"""04_buildings: the final building table, one footprint per building, a best height and a kind.

Footprints, chosen building by building (choose_footprints) from the sources in [sources] footprints: OSM's
hand-drawn buildings first; then a "blocks" source (GBA: whole buildings from 3 m imagery), kept where it is
compact and a "pieces" source (the East Asia footprints, 02b_eastasia) would only over-split it; then the
"pieces" source's footprints, which keep urban-village buildings apart where GBA merges them into blobs. A
footprint's height from a source with heights (GBA) is that of its polygon covering most of the footprint.

Height, first of [sources] heights that applies (column h_src records which); Shenzhen uses them all:
  landmark   hand-checked tower lists (paths.landmarks, data/landmarks*.csv), matched to the footprint under
             the point
  osm_height OSM height tag, from an OSM footprint that holds most of this one
  osm_levels OSM building:levels x level_h, same match rule
  blend      a weighted mean of two height sources inside a band of heights ([buildings.blend]; Shenzhen:
             15-30 m buildings get 0.35 GBA + 0.65 CNBH-10m, the more accurate source in that band, see
             checks/report.md)
  gba, ...   a footprint source's own estimate (the height sources are named after them)
  cnbh       the CNBH-10m raster (sources/cnbh.py), where nothing above gave a height
  default    buildings.default_floors x level_h
Heights are floored at buildings.min_h.

Kind (drives materials and roofs later), from the region preset's building_kind(): Shenzhen's are tower,
slab, podium, village, factory, house, midrise, civic, from OSM building tags where matched and from height
and footprint shape otherwise.

Writes buildings.gpkg (WGS84) in the data folder and checks/buildings.md.
"""
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely.affinity
from shapely.geometry import Point, Polygon

from .. import presets, sources
from ..common import (CFG, CHECKS, CITY, DATA, LEVEL_H, MIN_HEIGHT_DECKS, MIN_HEIGHT_TAGS, RAW, UNDERGROUND_DROP, UTM,
                      best_match, boundary, height_m, load_osm, underground_mask)

B = CFG["buildings"]
FOOTPRINTS = CFG["sources"]["footprints"]
HEIGHTS = CFG["sources"]["heights"]
LANDMARKS = sorted(CITY.glob(CFG["paths"]["landmarks"]))   # one hand-checked list per area
MIN_H = B["min_h"]
MIN_PIECE = B["min_piece"]    # m²; smaller footprints (and clipped leftovers) are dropped


def shape_stats(g: gpd.GeoDataFrame) -> pd.DataFrame:
    rect = g.geometry.minimum_rotated_rectangle()
    coords = rect.apply(lambda r: np.asarray(r.exterior.coords)[:3])
    sides = coords.apply(lambda c: sorted([np.hypot(*(c[1] - c[0])), np.hypot(*(c[2] - c[1]))]))
    short = sides.str[0].clip(lower=0.1)
    return pd.DataFrame({"area": g.area, "length": sides.str[1], "width": short,
                         "aspect": sides.str[1] / short}, index=g.index)


LANDMARK_CHECK = []           # (name, listed height, the data's height) for checks/buildings.md
LM = B["landmarks"]
# a height to the very top of the building (CTBUH's architectural height, a spire's or a lantern's tip): no part
# rises above it. A roof height leaves thin parts (masts, spires under 120 m²) above it alone
TOP_TYPES = ("tip", "spire", "architectural", "dome", "lantern", "tower", "pinnacle")


def main_roof(parts: gpd.GeoDataFrame, spire_area: float = 60.0) -> float:
    """The main roof of a building made of parts: going down from its top, the height at which its parts
    add up to spire_area m² (a spire or mast is thinner; a crown of a few small pieces is not)."""
    o = parts.assign(a=parts.area).sort_values("h", ascending=False)
    k = int(np.searchsorted(o.a.cumsum().values, spire_area))
    return float(o.h.iloc[min(k, len(o) - 1)])


def match_nearest(pts: gpd.GeoDataFrame, b: gpd.GeoDataFrame) -> pd.DataFrame:
    """The footprint under each point, else the nearest one within the radius; one row per footprint."""
    j = gpd.sjoin_nearest(pts, b[["geometry"]], max_distance=LM["radius"], distance_col="d")
    # two rows on one footprint: only one can set its height, so say which (a tower standing on a larger
    # building, such as Hoboken Terminal's clock tower on the station and its train shed, took the whole of it
    # to its tip; such a row wants use_height false, or a footprint of its own)
    for i, g in j.groupby("index_right"):
        if len(g) > 1:
            print(f"landmarks: {', '.join(g.sort_values('d').name_zh)} share one footprint; the first sets its height")
    j = j.sort_values("d")
    j = j[~j.index.duplicated()].drop_duplicates("index_right")
    return pd.DataFrame({"row": j.index, "k": j.index_right.values, "d": j.d.values})


def match_best(pts: gpd.GeoDataFrame, b: gpd.GeoDataFrame, part_of: pd.Series) -> pd.DataFrame:
    """Of the buildings within the radius of each point (a building made of OSM parts counts as one), the one
    whose data height is closest to the listed height, distance counting too: score = min(|ln(h / listed)|, 1)
    + distance / radius. The point often lies on a tower's podium or forecourt (La Défense's dalle: Tour
    Triangle's, Trinity's, Aurore's), 20-40 m from the tower; the podium, at a fifth of the height, scores
    worse than the tower beside it. Assigned greedily by score: one row per building, one building per row."""
    r = LM["radius"]
    zone = gpd.GeoDataFrame({"row": pts.index}, geometry=pts.buffer(r).values, crs=UTM)
    c = gpd.sjoin(zone, b[["geometry"]], predicate="intersects").rename(columns={"index_right": "k"})
    if not len(c):
        return pd.DataFrame(columns=["row", "k", "d"])
    c["d"] = [b.geometry[k].distance(pts.geometry[i]) for i, k in zip(c.row, c.k)]
    c["key"] = [("p", part_of[k]) if pd.notna(part_of[k]) else ("b", k) for k in c.k]
    roofs = {}
    for key in c.key.unique():
        if key[0] == "p":
            roofs[key] = main_roof(b[part_of == key[1]])
    c["h"] = [roofs[key] if key[0] == "p" else b.h[k] for key, k in zip(c.key, c.k)]
    # [buildings.landmarks] max_d, min_area: no building farther than max_d m from the point, nor (a plain
    # footprint, not one of parts) under min_area m²: a 179 m tower on a 189 m² fragment beside its site is a needle
    if LM.get("max_d", 0) > 0:
        c = c[c.d <= LM["max_d"]]
    if LM.get("min_area", 0) > 0:
        c = c[[key[0] == "p" or b.geometry[k].area >= LM["min_area"] for key, k in zip(c.key, c.k)]]
    if not len(c):
        return pd.DataFrame(columns=["row", "k", "d"])
    listed = pts["height_m"].reindex(c.row).values.astype(float)
    ratio = np.abs(np.log(np.clip(c.h.fillna(1).values, 1, None) / listed))
    c["score"] = np.minimum(ratio, 1.0) + c.d.values / r
    c = c.sort_values("score")
    rows, keys, out = set(), set(), []
    for t in c.itertuples():
        if t.row in rows or t.key in keys:
            continue
        rows.add(t.row)
        keys.add(t.key)
        out.append((t.row, t.k, t.d))
    return pd.DataFrame(out, columns=["row", "k", "d"])


def apply_landmarks(b: gpd.GeoDataFrame) -> int:
    """The landmark list's heights and names (see [buildings.landmarks] for how a row finds its building).
    A plain footprint takes the listed height (h_src landmark). A building made of OSM parts keeps their
    heights (setbacks, crown, spire) and only takes the name, on every part; with cap, no part rises above
    the listed height (for a roof height: no part over 120 m²)."""
    if not LANDMARKS:
        return 0
    lm = pd.concat([pd.read_csv(f) for f in LANDMARKS], ignore_index=True)
    lm["use_height"] = lm["use_height"].astype(str).str.lower().eq("true")
    feature = lm["feature"].fillna("building") if "feature" in lm else pd.Series("building", index=lm.index)
    # structures (the ferris wheel, the Eiffel Tower) and rows with an unverified position don't set building
    # heights; with cap, monuments (use_height false, feature building) name and cap theirs
    lm = lm[lm["use_height"] | (LM["cap"] & feature.eq("building"))].dropna(subset=["lat", "lon", "height_m"])
    pts = gpd.GeoDataFrame(lm, geometry=[Point(xy) for xy in zip(lm.lon, lm.lat)], crs="EPSG:4326").to_crs(UTM)
    part_of = b["part_of"] if "part_of" in b else pd.Series(np.nan, index=b.index)
    # ([osm] min_height: a deck is no landmark's building: the MBS SkyPark lies over its towers' points)
    bm = b[~b["osm_deck"].fillna(False).astype(bool)] if "osm_deck" in b else b
    j = match_best(pts, bm, part_of) if LM["match"] == "best" else match_nearest(pts, bm)
    if "landmark" not in b:
        b["landmark"] = None
    b["monument"] = False
    for row, k, d in zip(j.row, j.k, j.d):
        r = pts.loc[row]
        listed, name, use = float(r["height_m"]), r["name_zh"], bool(r["use_height"])
        top = any(t in str(r.get("height_type", "")).lower() for t in TOP_TYPES)
        hid = part_of[k]
        if pd.isna(hid):
            data_h, src = b.at[k, "h"], b.at[k, "h_src"]
            if use:
                rise = 0.0
                if LM.get("ground") == "point":       # the list's height is over the ground at the point, the
                    lo = dem_low([b.geometry[k]])[0]   # table's over the lowest ground under the outline
                    at = dem_low([r.geometry], points=True)[0]
                    rise = float(np.clip(at - lo, 0, 40)) if np.isfinite(at) and np.isfinite(lo) else 0.0
                    if rise > 0.5:
                        print(f"landmarks: {name}: {listed:.1f} m over the ground at its point, {rise:.1f} m over "
                              f"the lowest under its outline")
                b.at[k, "h"], b.at[k, "h_src"] = listed + rise, "landmark"
            elif top and data_h > listed + 1 and not (pd.to_numeric(b.at[k, "min_h"], errors="coerce") >= listed
                                                         if "min_h" in b else False):
                # (a raised roof whose underside is over the listed top, a courtyard's glass roof over a museum's
                # cornice, is not capped through itself)
                b.at[k, "h"], b.at[k, "h_src"] = listed, "landmark_cap"
            sel = [k]
        else:
            sel = part_of.index[part_of == hid]
            data_h, src = main_roof(b.loc[sel]), "parts (main roof)"
            hi = float(b.loc[sel, "h"].max())
            if use and LM.get("raise_parts", 0) and listed - hi > LM["raise_parts"]:
                k_ = listed / hi
                print(f"landmarks: {name}: {len(sel)} parts raised x{k_:.3f} to its {listed:.0f} m (top {hi:.0f} m)")
                b.loc[sel, "h"] = b.loc[sel, "h"] * k_
                if "min_h" in b:
                    b.loc[sel, "min_h"] = b.loc[sel, "min_h"].fillna(0) * k_
                data_h, src = main_roof(b.loc[sel]), f"parts raised from {hi:.0f}"
            if LM["cap"]:
                over = b.loc[sel, "h"] > listed + 1
                if not top:
                    over &= b.loc[sel].area >= 120
                if over.any():
                    idx = over[over].index
                    print(f"landmarks: {name}: {len(idx)} parts over its {listed:.0f} m capped "
                          f"(up to {b.loc[idx, 'h'].max():.0f} m)")
                    b.loc[idx, "h"] = listed
                    b.loc[idx, "h_src"] = "landmark_cap"
                    if "min_h" in b:          # a lifted piece wholly over the cap comes down onto the roof
                        down = idx
                        if LM.get("cap_keeps_lift"):     # (with cap_keeps_lift only those wholly over it)
                            down = idx[b.loc[idx, "min_h"].fillna(0).values >= listed - 1]
                        b.loc[down, "min_h"] = 0.0
        b.loc[sel, "name"] = name
        b.loc[sel, "landmark"] = name
        if not use:                          # a monument (the Opéra, the Invalides): the kinds keep it civic
            b.loc[sel, "monument"] = True
        LANDMARK_CHECK.append((name, listed, float(data_h), src, float(d)))
    return len(j)


OSM_MAX_AREA = B["osm_max_area"]      # larger tagged OSM polygons are usually whole estates, not one building
BIG_BUILDING_TAGS = set(B["big_building_tags"])  # ...except these, single large buildings (terminal, stadium, halls)


DECK_NAMES = r"(?i)bridge|deck|sky ?park"


def deck_rule(osm: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """[osm] min_height = "decks": an OSM building's min_height / building:min_level makes it a raised deck only
    when it is one: tagged building=bridge, named a bridge, deck or sky park (Canninghill Piers' skybridge), or
    lying half or more over two or more other buildings that reach its underside (less 3 m: the MBS SkyPark on its
    three towers; an upper storey drawn inside one tower's outline is no deck).
    Any other (a tower with building:min_level over the ring of its podium: Far East Plaza Residence at 18 m, City
    Gate Residences at 14 m) stands on the ground as without the tag. true: every one is raised."""
    if not MIN_HEIGHT_DECKS or "min_h_tag" not in osm:
        return osm
    import shapely
    up = osm.index[osm["min_h_tag"] > 0]
    if not len(up):
        return osm
    named = osm.loc[up, "name"].fillna("").str.contains(DECK_NAMES) | osm.loc[up, "building"].eq("bridge")
    j = gpd.sjoin(osm.loc[up, ["geometry"]].reset_index(names="d"), osm[["geometry"]].reset_index(names="u"),
                  predicate="intersects")
    j = j[(j.d != j.u) & ~j.u.isin(up)]
    j = j[osm["h"].reindex(j.u).fillna(0).values >= osm["min_h_tag"].reindex(j.d).values - 3.0]
    # (a building only touching it, or under a tenth of it, doesn't count)
    j = j[shapely.area(shapely.intersection(osm.geometry.reindex(j.d).values, osm.geometry.reindex(j.u).values))
          >= 0.1 * osm.area.reindex(j.d).values]
    over = pd.Series(0.0, index=up)
    if len(j):
        under = j.groupby("d").u.apply(lambda u: shapely.union_all(osm.geometry.loc[u.values].values))
        over.loc[under.index] = [osm.geometry[d].intersection(g).area / max(osm.geometry[d].area, 1e-6)
                                 for d, g in under.items()]
    n_under = j.groupby("d").size().reindex(up).fillna(0) if len(j) else pd.Series(0, index=up)
    deck = named | ((over >= 0.5) & (n_under >= 2))
    osm = osm.copy()
    osm.loc[up[~deck.values], "min_h_tag"] = np.nan
    print(f"min_height decks: {int(deck.sum())} of {len(up)} OSM buildings with a min_height are decks ("
          + ", ".join(f"{osm.at[i, 'osm_id']} {osm.at[i, 'name'] if pd.notna(osm.at[i, 'name']) else ''} "
                      f"{osm.at[i, 'min_h_tag']:g} m" for i in up[deck.values]) + "); the rest stand on the ground")
    return osm


def attach_osm(b: gpd.GeoDataFrame, osm: gpd.GeoDataFrame):
    """Copy OSM name, building tag and heights onto footprints.

    Name and tag come from the best-overlapping OSM building when IoU >= 0.5. Heights come from
    the OSM building (<= OSM_MAX_AREA) that holds most of the footprint (>= 50 % of it inside), so
    an OSM tower drawn as one polygon gives its height to every piece the 0.5 m data split it into.
    """
    m = best_match(b, osm, cols=())
    m = m[m.iou >= 0.5].set_index("ia")
    b["osm_id"] = m["ib"].map(osm["osm_id"])
    b["osm_building"] = m["ib"].map(osm["building"])
    b["name"] = m["ib"].map(osm["name"])
    if MIN_HEIGHT_TAGS and "min_h_tag" in osm:     # [osm] min_height: a matched building with a min_height is raised
        mh = m["ib"].map(osm["min_h_tag"])
        mh = mh[mh > 0]
        b["min_h"] = np.maximum(b["min_h"].fillna(0.0) if "min_h" in b else 0.0, mh.reindex(b.index).fillna(0.0))
        b["osm_deck"] = b.index.isin(mh.index)

    tagged = osm[osm["h"].notna() & (osm.area <= OSM_MAX_AREA)]
    h = best_match(b, tagged, cols=())
    h = h[h.inter / h.area_a >= 0.5].set_index("ia")
    b["h_osm_tag"] = h["ib"].map(tagged["h_tag"])
    b["h_osm_levels"] = h["ib"].map(tagged["h_levels"])
    b["osm_share"] = (h["inter"] / h["area_b"]).reindex(b.index)     # how much of that OSM building this is


def source_height(b: gpd.GeoDataFrame, gba: gpd.GeoDataFrame) -> pd.DataFrame:
    """Height of a height source's polygon (GBA) covering most of each footprint (>= NEEDLE cover of it): columns
    h, h_mean (the polygon's mean height, where the source has one: [sources.<name>] mean) and join ("largest",
    "weighted").

    A tall height (>= 40 m in Shenzhen) only transfers to a footprint of >= 250 m² or one covering >= 40 %
    of the source's polygon; otherwise small structures beside a tower would become needles.
    With [buildings.join] weighted > 0, a footprint no single polygon covers by NEEDLE cover (a block the source
    splits into many plots: London's Carbon & Place polygons are land-registry plots) takes the area-weighted
    median of the heights of the polygons covering it, where together they cover `weighted` of it or more.
    """
    m = best_match(b, gba, cols=())
    m = m[m.inter / m.area_a >= NEEDLE["cover"]].copy()
    m["h"] = m["ib"].map(gba["h"])
    needle = (m["h"] >= NEEDLE["height"]) & (m.area_a < NEEDLE["area"]) & (m.inter / m.area_b < NEEDLE["share"])
    m = m[~needle].set_index("ia")
    out = pd.DataFrame({"h": m["h"].reindex(b.index), "join": pd.Series("largest", index=m.index).reindex(b.index)})
    if "h_mean" in gba:
        out["h_mean"] = m["ib"].map(gba["h_mean"]).reindex(b.index)
    if JOIN["weighted"] > 0:
        rest = b.index[out["h"].isna()]
        if len(rest):
            w = weighted_height(b.loc[rest], gba)
            w = w[w.cover >= JOIN["weighted"]]
            out.loc[w.index, "h"] = w["h"]
            out.loc[w.index, "join"] = "weighted"
            if "h_mean" in out:
                out.loc[w.index, "h_mean"] = w["h_mean"]
            print(f"weighted join: {len(w):,} of {len(rest):,} footprints without a polygon covering "
                  f"{NEEDLE['cover']:.0%} of them get the area-weighted median of the polygons that cover "
                  f"{JOIN['weighted']:.0%}+ ({b.loc[w.index].area.sum() / 1e6:.2f} km²)")
    if JOIN.get("big", 0) > 0:
        rest = b.index[out["h"].isna() & (b.area >= JOIN["big"])]
        if len(rest):
            w = weighted_height(b.loc[rest], gba)
            w = w[w.cover > 0]
            out.loc[w.index, "h"] = w["h"]
            out.loc[w.index, "join"] = "big"
            if "h_mean" in out:
                out.loc[w.index, "h_mean"] = w["h_mean"]
            print(f"big join: {len(w):,} of {len(rest):,} footprints of {JOIN['big']:.0f} m² or more without a height "
                  f"get the area-weighted median of whatever polygons overlap them")
    return out


def weighted_height(b: gpd.GeoDataFrame, g: gpd.GeoDataFrame) -> pd.DataFrame:
    """Per footprint: the area-weighted median of the heights (h) of the polygons of g overlapping it, their
    area-weighted mean h_mean (where g has one), and the share of the footprint they cover (with a height)."""
    ov = gpd.overlay(b[["geometry"]].reset_index(names="ia"), g[["geometry"]].reset_index(names="ib"),
                     how="intersection", keep_geom_type=True)
    ov["w"] = ov.area
    ov["h"] = g["h"].reindex(ov.ib).values
    if "h_mean" in g:
        ov["hm"] = g["h_mean"].reindex(ov.ib).values
    ov = ov[ov.h.notna() & (ov.w > 0)].sort_values(["ia", "h"])
    if not len(ov):
        return pd.DataFrame(columns=["h", "h_mean", "cover"])
    cum = ov.groupby("ia").w.cumsum()
    tot = ov.groupby("ia").w.transform("sum")
    med = ov[cum >= 0.5 * tot].drop_duplicates("ia").set_index("ia")["h"]
    res = pd.DataFrame({"h": med, "cover": (ov.groupby("ia").w.sum() / b.area.reindex(med.index)).reindex(med.index)})
    if "hm" in ov:
        v = ov.dropna(subset=["hm"])
        res["h_mean"] = (v.hm * v.w).groupby(v.ia).sum() / v.w.groupby(v.ia).sum()
    return res


def lend_fields(b: gpd.GeoDataFrame, name: str, g: gpd.GeoDataFrame):
    """[sources.<name>] lend: the source's fields on the other footprints (another primary's, OSM's fill) from its
    polygon covering most of each (>= NEEDLE cover of it), where they have no value of their own."""
    cols = [c for c in CFG["sources"].get(name, {}).get("lend", []) if c in g]
    if not cols:
        return
    other = b.index[b["source"] != name]
    m = best_match(b.loc[other], g, cols=())
    m = m[m.inter / m.area_a >= NEEDLE["cover"]].set_index("ia")
    for c in cols:
        v = m["ib"].map(g[c]).reindex(b.index)
        b[c] = v if c not in b else b[c].where(b[c].notna(), v)
    print(f"lend: {name}'s {', '.join(cols)} on {len(m):,} other footprints")


NEEDLE = B["needle"]
JOIN = B["join"]
DUP_SHARE = B["dup_share"]    # a footprint overlapping an already chosen one by this much is the same
                              # building drawn a few metres off; clipping it would leave a lip beside it
ALIGN_CELL = B["align_cell"]  # m; East Asia offsets vary between imagery tiles, so correct them per cell


def align_pieces(ea: gpd.GeoDataFrame, ref: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Shift a pieces source's footprints (East Asia) onto OSM, with a median offset per ALIGN_CELL cell.

    Offsets come from nearest-centroid pairs of buildings > 150 m² less than 25 m apart; cells with
    fewer than 30 pairs use the district-wide median.
    """
    a = gpd.GeoDataFrame(geometry=ea[ea.area > 150].centroid, crs=UTM)
    r = gpd.GeoDataFrame(geometry=ref[ref.area > 150].centroid, crs=UTM)
    j = gpd.sjoin_nearest(a, r, max_distance=25, distance_col="d")
    j = j[~j.index.duplicated()]
    dx = r.geometry.x.loc[j.index_right].values - j.geometry.x.values
    dy = r.geometry.y.loc[j.index_right].values - j.geometry.y.values
    cell = lambda x, y: (np.floor(x / ALIGN_CELL).astype(int), np.floor(y / ALIGN_CELL).astype(int))
    cx, cy = cell(j.geometry.x.values, j.geometry.y.values)
    off = pd.DataFrame({"cx": cx, "cy": cy, "dx": dx, "dy": dy}).groupby(["cx", "cy"]).agg(
        dx=("dx", "median"), dy=("dy", "median"), n=("dx", "size"))
    off = off[off.n >= 30]
    gdx, gdy = np.median(dx), np.median(dy)
    c = ea.centroid
    ex, ey = cell(c.x.values, c.y.values)
    key = pd.MultiIndex.from_arrays([ex, ey])
    sx = off["dx"].reindex(key).fillna(gdx).values
    sy = off["dy"].reindex(key).fillna(gdy).values
    out = ea.copy()
    out["geometry"] = [shapely.affinity.translate(g, x, y) for g, x, y in zip(ea.geometry, sx, sy)]
    print(f"pieces alignment: district median shift ({gdx:+.1f}, {gdy:+.1f}) m; "
          f"{len(off)} cells corrected, |shift| p50/p90 {np.percentile(np.hypot(sx, sy), [50, 90]).round(1)} m")
    return out


def pieces_inside(hosts: gpd.GeoDataFrame, ea: gpd.GeoDataFrame, frac: float = 0.5) -> pd.DataFrame:
    """Pairs (host, East Asia piece) where >= frac of the piece lies inside the host."""
    ov = gpd.overlay(hosts[["geometry"]].reset_index(names="ih"), ea[["geometry"]].reset_index(names="ie"),
                     how="intersection", keep_geom_type=True)
    ov = ov[ov.area / ea.area.loc[ov.ie].values >= frac]
    return pd.DataFrame({"ih": ov.ih.values, "ie": ov.ie.values, "piece_area": ea.area.loc[ov.ie].values})


def drop_osm_containers(osm: gpd.GeoDataFrame, keep=frozenset(), inner: bool = False,
                        aside=frozenset()) -> gpd.GeoDataFrame:
    """Remove OSM polygons that outline a compound or duplicate another OSM building.

    A polygon holding >= 2 other OSM buildings (>= 80 % inside it) is an estate outline; of two
    OSM polygons overlapping by more than half of the smaller, the smaller one is a duplicate part.
    keep: indices never dropped (an outline its building:parts draw, [buildings] keep): the buildings inside
    them go as their duplicates. inner ([buildings] container_inner): a building is no duplicate of an estate
    outline that goes itself (by default both go, and the block is left to the other sources). aside: indices
    neither dropped nor counted ([osm] min_height decks: no estate outline, and the towers under one are no
    duplicates of it).
    """
    ov = gpd.overlay(osm[["geometry"]].reset_index(names="io"), osm[["geometry"]].reset_index(names="ii"),
                     how="intersection", keep_geom_type=True)
    ov = ov[ov.io != ov.ii]
    if aside:
        ov = ov[~ov.io.isin(aside) & ~ov.ii.isin(aside)]
    area = osm.area
    inside = ov[ov.area / area.loc[ov.ii].values >= 0.8]
    containers = inside.groupby("io").size()
    containers = set(containers[containers >= 2].index) - set(keep)
    pairs = ov[ov.area / np.minimum(area.loc[ov.io].values, area.loc[ov.ii].values) > 0.5]
    if inner:                   # beside an outline that goes anyway, a building is no duplicate
        pairs = pairs[~pairs.io.isin(containers) & ~pairs.ii.isin(containers)]
    smaller = {ii if area[ii] < area[io] else io for io, ii in zip(pairs.io, pairs.ii)}
    if keep:                    # a kept outline is no duplicate of one that is not (what it holds is); of two kept
        k = set(keep)           # ones (a tower's outline in its site's, both drawn by parts) the smaller goes
        smaller = set()
        for io, ii in zip(pairs.io, pairs.ii):
            s_, o_ = (ii, io) if area[ii] < area[io] else (io, ii)
            smaller.add(o_ if (s_ in k and o_ not in k) else s_)
    drop = containers | (smaller - containers)
    return osm.drop(index=[i for i in drop if i in osm.index])


RULES = B["rules"]
RULE_COUNTS = []              # (source, label, action, n, area m²) for checks/buildings.md
_DROPPED = []                 # what a primary's rules drop: no other source builds there (choose_footprints)


def primary_rules(g: gpd.GeoDataFrame, name: str, named_only: bool = False) -> gpd.GeoDataFrame:
    """[buildings] rules on a primary source's footprints (its own height in h): the first rule whose conditions
    all hold decides. A rule's conditions: source (the primary's name), field with values (exact, compared as
    text) or prefix (text prefixes), h_below / h_from (m), area_below / area_from (m²). Its action: "drop"; "keep"
    (column keep_small: no min_piece or 3 m strip rule; a cadastre's 8 m² stair tower or 2.5 m wide bay is part of
    its building, and leaving it out leaves a gap); "exact" (keep, and h_exact: its own height, not floored at
    min_h: a memorial's 0.5-4.7 m stelae); "roof" (keep, h_exact, and min_h: a canopy or hall roof is drawn as its
    roof, raised from `thick` m under its eave over open ground, not as a block from the ground). Column `rule` names
    the rule (its label, else its action). A fill source's polygons take only the rules that name it (source), and
    only their drops matter (the Umweltatlas's copies of the canopies the LoD2's rules drop)."""
    # (a fill source, named_only: only the rules naming it)
    rules = [r for r in RULES if r.get("source", None if named_only else name) == name]
    g = g.assign(rule=None, keep_small=False, h_exact=False)
    if not rules:
        return g
    area = g.area
    h = pd.to_numeric(g["h"], errors="coerce") if "h" in g else pd.Series(np.nan, index=g.index)
    free = pd.Series(True, index=g.index)
    drop = pd.Series(False, index=g.index)
    for r in rules:
        m = free.copy()
        if "field" in r:
            v = g[r["field"]].astype(str) if r["field"] in g else pd.Series("", index=g.index)
            if "values" in r:
                m &= v.str.lower().isin([str(x).lower() for x in r["values"]])
            if "prefix" in r:
                m &= v.str.startswith(tuple(str(x) for x in r["prefix"]))
        if "h_below" in r:
            m &= h.fillna(0) < r["h_below"]
        if "h_from" in r:
            m &= h.fillna(0) >= r["h_from"]
        if "area_below" in r:
            m &= area < r["area_below"]
        if "area_from" in r:
            m &= area >= r["area_from"]
        act = r.get("action", "keep")
        label = r.get("label", act)
        g.loc[m, "rule"] = label
        if act == "drop":
            drop |= m
        else:
            g.loc[m, "keep_small"] = True
        if act in ("exact", "roof"):
            g.loc[m, "h_exact"] = True
        if act == "roof":
            top = h[m]
            eave = top
            if "eave_z" in g and "ground_elevation" in g:
                eave = (pd.to_numeric(g.loc[m, "eave_z"], errors="coerce")
                        - pd.to_numeric(g.loc[m, "ground_elevation"], errors="coerce")).fillna(top).clip(upper=top)
            if "min_h" not in g:
                g["min_h"] = np.nan
            g.loc[m, "min_h"] = (eave - r.get("thick", 0.6)).clip(lower=0).round(2)
        RULE_COUNTS.append((name, label, act, int(m.sum()), float(area[m].sum())))
        if act == "drop" and not named_only:
            _DROPPED.extend(g.geometry[m].make_valid())
        free &= ~m
    print(f"rules {name}: " + "; ".join(f"{lab} ({act}) {n:,}" for s, lab, act, n, a in RULE_COUNTS if s == name))
    return g[~drop]


def cleanup(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Drop non-OSM strips under 3 m wide (clipping leftovers; not what [buildings] rules keep) and repair invalid
    geometry."""
    b = b.copy()
    b["geometry"] = b.geometry.make_valid()
    b = b[b.geom_type.isin(["Polygon", "MultiPolygon"])]
    rect = b.geometry.minimum_rotated_rectangle()
    width = rect.apply(lambda r: min(np.hypot(*np.diff(np.asarray(r.exterior.coords)[:3], axis=0).T)))
    strip = (width < 3) & (b.source != "osm")
    if "keep_small" in b:
        strip &= ~b["keep_small"].fillna(False).astype(bool)
    print(f"cleanup: dropped {strip.sum():,} strips under 3 m wide")
    return b[~strip].reset_index(drop=True)


SPLIT = B["split"]


def split_merged(pg: gpd.GeoDataFrame, osm: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Primary footprints drawn as one polygon over buildings OSM maps apart ([buildings] split): official
    cadastres sometimes join a tower and its podium, or a block of stores and the tower over it, under one
    number and give the whole the tower's roof (Manhattan: the Hudson Yards shops and 30 Hudson Yards as
    18,000 m² at 386 m). Where at least `min_n` OSM buildings lie mostly (half or more) inside one, cover
    `cover` of it and their heights differ by `ratio` or more, the OSM buildings (clipped to it) replace it,
    each with its own OSM height (column h_split)."""
    if not SPLIT or osm is None:
        return pg.assign(h_split=np.nan)
    o = drop_osm_containers(osm[osm["h"].notna() & (osm["h"] > 0)])
    ov = gpd.overlay(pg[["geometry"]].reset_index(names="ip"), o[["geometry"]].reset_index(names="io"),
                     how="intersection", keep_geom_type=True)
    ov["a"] = ov.area
    ov = ov[ov.a >= 0.5 * o.area.loc[ov.io].values]
    ov["h"] = o["h"].loc[ov.io].values
    g = ov.groupby("ip").agg(n=("io", "size"), a=("a", "sum"), hmin=("h", "min"), hmax=("h", "max"))
    g = g[(g.n >= SPLIT["min_n"]) & (g.a >= SPLIT["cover"] * pg.area.loc[g.index]) &
          (g.hmax >= SPLIT["ratio"] * g.hmin.clip(lower=1))]
    rows = []
    if not len(g):                      # nothing to split
        print("split: no primary footprint over several OSM buildings")
        return pg.assign(h_split=np.nan)
    for ip in g.index:
        pieces = ov[ov.ip == ip]
        for r in pieces.itertuples():
            rows.append({**pg.loc[ip].drop("geometry").to_dict(), "h": np.nan, "h_split": r.h, "split_of": ip,
                         "geometry": r.geometry})
        # what the OSM buildings leave of it: at the lowest of their heights
        rest = pg.geometry[ip].difference(pieces.geometry.union_all()).buffer(-1, join_style=2).buffer(1, join_style=2)
        if not rest.is_empty and rest.area >= MIN_PIECE:
            rows.append({**pg.loc[ip].drop("geometry").to_dict(), "h": np.nan, "h_split": pieces.h.min(),
                         "split_of": ip, "geometry": rest})
    out = gpd.GeoDataFrame(pd.concat([pg.drop(index=g.index).assign(h_split=np.nan),
                                      gpd.GeoDataFrame(rows, crs=UTM)], ignore_index=True), crs=UTM)
    print(f"split: {len(g):,} primary footprints over several OSM buildings replaced by {len(rows):,} of them")
    return out


FILL_MAX_H = B["fill_max_h"]


FILL = B["fill"]


def osm_areas(selectors: list) -> "shapely.Geometry | None":
    """The union of the OSM areas (ways and relations) matching `key=value` selectors over the districts' box."""
    from shapely.geometry import box
    from ..common import element_geoms, overpass
    s, w, n, e = gpd.GeoSeries([box(*boundary().total_bounds)], crs=UTM).to_crs("EPSG:4326").total_bounds[[1, 0, 3, 2]]
    sel = "".join(f'way["{k}"="{v}"];rel["{k}"="{v}"];' for k, v in (x.split("=", 1) for x in selectors))
    res = overpass(f"[out:json][timeout:600][bbox:{s:.5f},{w:.5f},{n:.5f},{e:.5f}];({sel});out geom;")
    geo = [g for _, g in element_geoms(res) if g.geom_type in ("Polygon", "MultiPolygon")]
    if not geo:
        return None
    return gpd.GeoSeries(geo, crs="EPSG:4326").to_crs(UTM).make_valid().union_all()


def fill_filter(g: gpd.GeoDataFrame, name: str) -> gpd.GeoDataFrame:
    """[buildings.fill]: which of a "fill" source's polygons may become buildings (where OSM has none), lying not
    mostly (half) on an OSM building that osm_skip leaves out (a canopy, a ship, a building site) or that exclude.osm
    leaves out (with exclude_inside), and at least
    min_area m² and min_h m tall (a height source's own h; unknown counts as 0), not tagged with one of
    [buildings] osm_skip in its `building` field (sources that copy OSM's tags: canopies, ships, building
    sites), and not standing (by its representative point) in an OSM area of `not_in` (["landuse=construction"]:
    the lidar's buildings since demolished)."""
    if not FILL:
        return g
    keep = pd.Series(g.area >= FILL.get("min_area", 0), index=g.index)
    if FILL.get("min_h", 0) > 0 and "h" in g:
        keep &= g["h"].fillna(0) >= FILL["min_h"]
    tags = 0
    if FILL.get("skip_tags") and "building" in g:
        t = g["building"].isin(B["osm_skip"])
        tags = int((keep & t).sum())
        keep &= ~t
    gone = 0
    if FILL.get("not_in"):
        u = osm_areas(FILL["not_in"])
        if u is not None:
            t = g.geometry.representative_point().within(u)
            gone = int((keep & t).sum())
            keep &= ~t
    excl = 0
    # nor where OSM maps something that is not a block (osm_skip: a station's canopy, a ship, a building site)
    # or an outline left out by id (with exclude_inside: the London Eye)
    out = list(_SKIPPED) + (list(_EXCLUDED) if B["exclude_inside"] else [])
    if out:
        u = gpd.GeoSeries(out, crs=UTM).buffer(1.0).union_all()
        near = g.geometry.intersects(u)
        t = pd.Series(False, index=g.index)
        t[near] = g.geometry[near].intersection(u).area >= 0.5 * g.geometry[near].area
        excl = int((keep & t).sum())
        keep &= ~t
    print(f"fill {name}: {int(keep.sum()):,} of {len(g):,} polygons may fill ({int((~keep).sum()):,} out: "
          f"{tags:,} by tag, {excl:,} on OSM's skipped or excluded buildings, "
          f"{gone:,} in {', '.join(FILL.get('not_in', [])) or '-'}, the rest under "
          f"{FILL.get('min_area', 0)} m² or {FILL.get('min_h', 0)} m)")
    return g[keep]


def choose_footprints(osm, blocks=(), pieces=(), primary=None) -> gpd.GeoDataFrame:
    """Pick, building by building, the footprint source to trust.

    0. primary (name, footprints), e.g. NYC's official footprints: every one of them is chosen, and OSM then
       only adds buildings they lack (an OSM polygon overlapping them by DUP_SHARE or more is the same
       building); blocks and pieces fill what is left, as below. Several primaries (a list; Paris: APUR in
       the arrondissements, BD TOPO in La Défense and Neuilly) each rule in their own districts
       ([sources.<name>] districts, by a footprint's representative point), a later one's footprints
       overlapping an earlier one's by DUP_SHARE dropped.

    1. OSM buildings up to OSM_MAX_AREA, and larger ones tagged or named as a single building
       (BIG_BUILDING_TAGS): drawn by people, usually one polygon per building.
    2. blocks (name, footprints), e.g. GBA: footprints not already taken by OSM, which, when a pieces
       source exists, are compact (solidity >= 0.75) and hold at most 3 of its pieces: the 0.5 m data
       over-split a single building, so keep it whole. A footprint over several small pieces (median
       < 150 m²) is a merged village block instead.
    3. pieces (name, footprints), e.g. East Asia: footprints that overlap no footprint chosen above by
       DUP_SHARE or more (those are the same building, drawn slightly offset), clipped where they still
       touch one.
    Blocks overlapping OSM by DUP_SHARE or more are likewise dropped in favour of OSM.
    """
    # big OSM polygons are usually estate outlines, unless tagged or named as one large building
    if osm is not None:
        big_one = osm["building"].isin(BIG_BUILDING_TAGS) | osm["name"].notna()
        # [buildings] keep (by id) and part_outlines (outlines their building:parts draw): kept at any size,
        # and never dropped as estates
        kept = set(osm.index[osm["osm_id"].isin(KEEP_OSM)]) if "osm_id" in osm else set()
        kept |= set(_PART_OUTLINES) & set(osm.index)
        if MIN_HEIGHT_TAGS and "min_h_tag" in osm:    # a deck mapped with min_height is no estate, nor a duplicate
            kept |= set(osm.index[osm["min_h_tag"] > 0])
        big_one |= osm.index.isin(list(kept))
        # a deck is no estate outline, and the towers under it are no duplicates of it (MBS's three towers went as
        # the SkyPark's smaller duplicates): it is set aside from the estate and duplicate rules
        aside = set(osm.index[osm["min_h_tag"] > 0]) if MIN_HEIGHT_TAGS and "min_h_tag" in osm else set()
        osm_keep = drop_osm_containers(osm[(osm.area <= OSM_MAX_AREA) | big_one], keep=kept,
                                       inner=B["container_inner"], aside=aside)
        chosen = gpd.GeoDataFrame({"source": "osm"}, index=osm_keep.index, geometry=osm_keep.geometry, crs=UTM)
    else:
        chosen = gpd.GeoDataFrame({"source": []}, geometry=[], crs=UTM)
    if primary is not None:
        prims = primary if isinstance(primary, list) else [primary]
        name = "+".join(n for n, _ in prims)
        firsts, covers = [], []
        for pname, pg in prims:
            f = gpd.GeoDataFrame({"source": pname, "pid": pg.index, "h_split": pg["h_split"].values,
                                  "keep_small": pg["keep_small"].values if "keep_small" in pg else False},
                                 geometry=pg.geometry.values, crs=UTM)
            # the districts the primary layer covers ([sources.<name>] districts; all by default): beyond them
            # (New Jersey beside New York City's layer) OSM is the footprint source, whole
            cover_names = CFG["sources"].get(pname, {}).get("districts")
            cover = None
            if cover_names:
                from ..common import districts
                dd = districts()
                cover = dd[dd.name.isin(cover_names)].geometry.union_all()
                if len(prims) > 1:          # several primaries: each only in its own districts
                    f = f[f.geometry.representative_point().within(cover)]
            if firsts and len(f):           # the same building from two layers along their districts' edge
                prev = gpd.GeoDataFrame(pd.concat(firsts, ignore_index=True), crs=UTM)
                ov = gpd.overlay(f[["geometry"]].reset_index(names="i_f"), prev[["geometry"]], how="intersection",
                                 keep_geom_type=True)
                share = ov.area.groupby(ov.i_f).sum().reindex(f.index).fillna(0) / f.area
                f = f[share < DUP_SHARE]
            firsts.append(f)
            covers.append(cover)
        first = gpd.GeoDataFrame(pd.concat(firsts, ignore_index=True), crs=UTM)
        cover = None if any(c is None for c in covers) else shapely.union_all(covers)
        outside = None
        if cover is not None and len(chosen):
            inside = chosen.geometry.representative_point().within(cover)
            outside, chosen = chosen[~inside], chosen[inside]
        if len(chosen):
            # (what the primary's rules dropped counts as the primary's: a canopy, a terrace, a garage roof at the
            # ground is no gap for OSM to fill)
            said = first[["geometry"]] if not _DROPPED else gpd.GeoDataFrame(
                geometry=list(first.geometry) + _DROPPED, crs=UTM)
            ov = gpd.overlay(chosen[["geometry"]].reset_index(names="io"), said, how="intersection",
                             keep_geom_type=True)
            share = ov.area.groupby(ov.io).sum().reindex(chosen.index).fillna(0) / chosen.area
            fill = chosen[share < DUP_SHARE]
            # an official layer is current: a tall OSM building it lacks is more likely gone (Manhattan's
            # detention complex, ABC's West 66th Street buildings), and a big untagged one a ship, a stage or
            # a bridge's tower; small low ones (sheds, kiosks, pier houses) are real gaps
            fh = osm["h"].reindex(fill.index)
            fname = osm["name"].reindex(fill.index).fillna("")
            ok = ((fh.isna() & (fill.area <= 300)) | (fh < FILL_MAX_H)) & ~fname.str.contains("Bridge", case=False)
            # [buildings] keep: built over the primary (a tower since its snapshot), which is clipped around them
            kept = chosen[osm["osm_id"].reindex(chosen.index).isin(KEEP_OSM).values] if KEEP_OSM else chosen.iloc[:0]
            fill = fill[ok & ~fill.index.isin(kept.index)]
            fill = gpd.overlay(fill, first[["geometry"]], how="difference", keep_geom_type=True)
            if len(kept):
                a0 = first.area
                ku = kept.geometry.union_all()
                cut = first.geometry.copy()
                near = cut.intersects(ku)
                cut[near] = cut[near].difference(ku).buffer(-0.5, join_style=2).buffer(0.5, join_style=2)
                gone = near & (cut.is_empty | (cut.area < np.maximum(MIN_PIECE, 0.3 * a0)))
                hit = near & ~gone
                print(f"keep: {len(kept)} OSM buildings over {name}: {int(gone.sum())} of its footprints under them "
                      f"go, {int(hit.sum())} clipped")
                first = first.assign(geometry=cut)[~gone]
                fill = gpd.GeoDataFrame(pd.concat([fill, kept], ignore_index=True), crs=UTM)
            print(f"primary {name}: {len(first):,} footprints; OSM adds {len(fill):,} they lack")
            chosen = gpd.GeoDataFrame(pd.concat([first, fill], ignore_index=True), crs=UTM)
        else:
            chosen = first
        if outside is not None and len(outside):
            print(f"beyond {name}'s districts: {len(outside):,} OSM footprints")
            chosen = gpd.GeoDataFrame(pd.concat([chosen, outside.reset_index(drop=True)], ignore_index=True), crs=UTM)
    fine = pieces[0][1] if pieces else None

    parts = [chosen]
    for name, g in blocks:
        if name in _FILLS:
            g = fill_filter(g, name)
        taken = parts[0] if len(parts) == 1 else gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=UTM)
        if _DROPPED:              # nor for a fill source
            taken = gpd.GeoDataFrame(pd.concat([taken[["geometry"]], gpd.GeoDataFrame(geometry=_DROPPED, crs=UTM)],
                                               ignore_index=True), crs=UTM)
        g = g.copy()
        g["solidity"] = g.area / g.convex_hull.area
        in_osm = gpd.overlay(g[["geometry"]].reset_index(names="ig"), taken[["geometry"]],
                             how="intersection", keep_geom_type=True)
        osm_frac = in_osm.area.groupby(in_osm.ig).sum().reindex(g.index).fillna(0) / g.area
        keep = osm_frac < DUP_SHARE
        if fine is not None:
            pairs = pieces_inside(g, fine)
            n = pairs.groupby("ih").size().reindex(g.index).fillna(0)
            med = pairs.groupby("ih").piece_area.median().reindex(g.index)
            village = (n >= 2) & (med < 150)
            keep = keep & (g.solidity >= 0.75) & (n <= 3) & ~village
        gba_keep = g[keep]

        # overlay(difference) clips each footprint only against the ones it touches (spatial index)
        label = f"{name}_" + gba_keep["source"].astype(str) if "source" in gba_keep else name
        if "source" in gba_keep and gba_keep["source"].eq(name).all():     # a file source names itself
            label = name
        gba_keep = gpd.GeoDataFrame({"source": label}, index=gba_keep.index, geometry=gba_keep.geometry, crs=UTM)
        gba_keep = gpd.overlay(gba_keep, taken[["geometry"]], how="difference", keep_geom_type=True)  # OSM wins
        parts.append(gba_keep)
    chosen = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=UTM)
    if "keep_small" in chosen:
        chosen["keep_small"] = chosen["keep_small"].fillna(False).astype(bool)
        chosen = chosen[(chosen.area >= MIN_PIECE) | chosen["keep_small"]]
    else:
        chosen = chosen[chosen.area >= MIN_PIECE]

    for name, ea in pieces:
        # overlap summed over all chosen footprints, so a piece straddling two of them also counts
        ov = gpd.overlay(chosen[["geometry"]], ea[["geometry"]].reset_index(names="ie"), how="intersection",
                         keep_geom_type=True)
        share = ov.area.groupby(ov.ie).sum() / ea.area.loc[ov.ie.unique()].reindex(ov.ie.unique())
        used = set(share[share >= DUP_SHARE].index)
        rest = ea.drop(index=list(used))
        rest = gpd.GeoDataFrame({"source": name}, index=rest.index, geometry=rest.geometry, crs=UTM)
        rest = gpd.overlay(rest, chosen[["geometry"]], how="difference", keep_geom_type=True)
        rest = rest[rest.area >= MIN_PIECE]
        chosen = gpd.GeoDataFrame(pd.concat([chosen, rest], ignore_index=True), crs=UTM)
    return cleanup(chosen)


LIFT = B["lift_parts"]        # raised parts over their own footprint float when nothing is under them (see use_parts)
LIFT_GAPS = LIFT == "gaps"    # ... only over a real gap in the building (see use_parts)
SHAFTS = float(B.get("parts_fill_shafts", 0.0) or 0.0)   # > 0: enclosed part_rest shafts filled (see fill_shafts)
PART_COVER = 0.25             # a building is made of its OSM parts when they cover this share of it


def num(v: pd.Series) -> pd.Series:
    return v.map(height_m).astype(float)


EXCLUDE_OSM = set(B["exclude"].get("osm", []))       # OSM ids ("w5013364", "r4114842") never built
KEEP_OSM = set(B["keep"].get("osm", []))             # OSM ids always built (whatever osm_skip or the estate rule say)
SURFACE = ("surface", "overground", "roof", "rooftop")   # location tags of buildings above ground despite a layer < 0
OSM_FIX = {str(k): float(v) for k, v in B["osm_fix"].items()}    # OSM id -> height replacing its tag


_FILLS = set()                # the "fill" sources among the blocks (filtered by fill_filter in choose_footprints)
_SKIPPED = []                 # outlines of the OSM buildings osm_skip leaves out (no fill on them, fill_filter)
_EXCLUDED = []                # outlines of the OSM buildings and parts left out by id (for exclude_inside)
_PART_OUTLINES = set()        # OSM buildings their building:parts cover by [buildings] part_outlines (part_outlines())


def set_heights(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """[buildings] set_h (OSM id -> m; {}: off): the final top of the table's pieces of that OSM building, after
    every other rule (landmarks, spikes, podium splits): one piece takes the height, several (an outline drawn
    as its parts, or split along a fill source's plots) are scaled, undersides too, so that the tallest reaches
    it; an outline no piece carries the id of takes the pieces inside it. For what neither a tag nor the lidar
    gets right: a station's train shed at the lidar's maximum (a
    neighbour's edge, a crane), a ministry at levels x 3.2 m under its tall civic storeys."""
    want = {str(k): float(v) for k, v in B.get("set_h", {}).items()}
    if not want or "osm_id" not in b:
        return b
    n = 0
    for oid, h in want.items():
        rows = b.index[(b["osm_id"] == oid).values]
        if not len(rows):
            # the outline lost to another source's pieces (King's Cross: a Carbon & Place plot over the station
            # OSM tags layer=1): the pieces whose inside point lies in it
            import pyogrio
            o = pyogrio.read_dataframe(DATA / "osm_buildings.gpkg", where=f"osm_id = '{oid}'")
            if len(o):
                g = o.to_crs(b.crs).geometry.make_valid().union_all()
                rows = b.index[b.geometry.representative_point().within(g).values]
        if not len(rows):
            print(f"set_h: no piece of {oid} in the table")
            continue
        top = float(b.loc[rows, "h"].max())
        k = h / max(top, 0.1)
        b.loc[rows, "h"] = (b.loc[rows, "h"] * k).round(1)
        if "min_h" in b:
            b.loc[rows, "min_h"] = (b.loc[rows, "min_h"].fillna(0.0) * k).round(1)
        b.loc[rows, "h_src"] = "set_h"
        n += len(rows)
    print(f"set_h: {n} pieces of {len(want)} OSM buildings set")
    return b


def part_outlines(osm: gpd.GeoDataFrame) -> set:
    """[buildings] part_outlines (a share; 0: off): the OSM buildings whose building:parts (those lying half or
    more inside them) cover this share of them or more. Such an outline is one building however large or
    whatever OSM buildings it holds (the National Gallery's 11,000 m², 100 Bishopsgate's site): its parts draw
    it (use_parts), the buildings inside it go as its duplicates."""
    share = B["part_outlines"]
    f = DATA / "osm_parts.gpkg"
    if not share or not f.exists() or not B["parts"]:
        return set()
    p = gpd.read_file(f).to_crs(UTM)
    p = p[~p["osm_id"].isin(EXCLUDE_OSM) & p.geometry.notna()]
    p["geometry"] = p.geometry.make_valid()
    ov = gpd.overlay(osm[["geometry"]].reset_index(names="io"), p[["geometry"]].reset_index(names="ip"),
                     how="intersection", keep_geom_type=True)
    ov = ov[ov.area >= 0.5 * p.area.reindex(ov.ip).values]
    if not len(ov):
        return set()
    cov = ov.dissolve("io").area / osm.area.reindex(ov.io.unique()).reindex(ov.dissolve("io").index)
    out = set(cov[cov >= share].index)
    big = [i for i in out if osm.area[i] > OSM_MAX_AREA]
    print(f"part outlines: {len(out):,} OSM buildings drawn by their parts ({share:.0%}+ covered), "
          f"{len(big)} of them over {OSM_MAX_AREA:.0f} m²")
    return out


def surface_layers(osm_all: gpd.GeoDataFrame, fills: list) -> gpd.GeoDataFrame:
    """[buildings] surface_layers: the OSM buildings with a layer under 0 that stand above ground anyway: tagged
    location=surface (or overground, roof; Victoria Station's layer=-2), or untagged with a fill source's
    polygon of [buildings.fill] min_h or more covering half of it (Crossrail Place, layer=-1 over the dock).
    location=underground always goes."""
    layer = pd.to_numeric(osm_all["layer"], errors="coerce").fillna(0)
    loc = osm_all["location"].fillna("")
    cand = osm_all[(layer < 0) & (loc != "underground")]
    keep = cand["location"].isin(SURFACE)
    rest = cand[cand["location"].isna()]
    if len(rest) and fills:
        g = gpd.GeoDataFrame(pd.concat([f[["geometry", "h"]] for f in fills], ignore_index=True), crs=UTM)
        g = g[g["h"].fillna(0) >= (FILL.get("min_h", 0) if FILL else 0)]
        ov = gpd.overlay(rest[["geometry"]].reset_index(names="io"), g[["geometry"]], how="intersection",
                         keep_geom_type=True)
        cov = ov.area.groupby(ov.io).sum() / rest.area.reindex(ov.io.unique()).reindex(ov.area.groupby(ov.io).sum().index)
        keep[cov[cov >= 0.5].index] = True
    out = cand[keep]
    print(f"surface layers: {len(out):,} of {len(cand):,} OSM buildings with a layer under 0 stand above ground "
          f"({int(out['location'].isin(SURFACE).sum())} by their location tag): "
          + ", ".join(out["name"].dropna().head(8)))
    return out


STATION_TYPES = ("train_station", "transportation")
STATION_MIN_AREA = 150.0      # m²: smaller untagged ones are entrances and kiosks, left to the usual estimate
_ST = str(B.get("station_untagged", "")).strip().lower()
STATION_DROP = _ST == "drop"
try:
    STATION_H = float(_ST) if _ST and not STATION_DROP else None
except ValueError:
    raise ValueError(f'[buildings] station_untagged = {_ST!r}: "drop", "<metres>" or ""') from None
_STATION_IDS = set()          # the untagged station outlines of this run (station_untagged = "<metres>")


def untagged_stations(osm: gpd.GeoDataFrame) -> pd.Series:
    """[buildings] station_untagged: the OSM building=train_station|transportation outlines of 150 m² or more with
    no height and no levels (the underground station boxes a mapper outlined, the entrance sheds), not listed in
    [buildings] keep and holding no building:part (those draw the building)."""
    m = osm["building"].isin(STATION_TYPES) & osm["h"].isna() & (osm.area >= STATION_MIN_AREA) \
        & ~osm["osm_id"].isin(KEEP_OSM)
    f = DATA / "osm_parts.gpkg"
    if m.any() and B["parts"] and f.exists():
        p = gpd.read_file(f).to_crs(UTM)
        p = p[p.geometry.notna() & ~p.geometry.is_empty]
        if len(p):
            pts = gpd.GeoDataFrame(geometry=p.geometry.make_valid().representative_point(), crs=UTM)
            j = gpd.sjoin(osm.loc[m, ["geometry"]], pts, predicate="contains")
            m &= ~osm.index.isin(j.index.unique())
    return m


def station_sheds(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """[buildings] station_untagged = "<metres>": the pieces of the untagged station outlines (untagged_stations)
    stand that high (h_src station), after every height estimate, which never saw it; landmarks and fix_h win."""
    if STATION_H is None or not _STATION_IDS or "osm_id" not in b:
        return b
    sel = (b["source"] == "osm") & b["osm_id"].isin(_STATION_IDS) & ~b["h_src"].isin(["landmark", "landmark_cap", "fix_h"])
    b.loc[sel, "h"] = STATION_H
    b.loc[sel, "h_src"] = "station"
    print(f"station_untagged: {int(sel.sum())} untagged station outlines set to {STATION_H:g} m")
    return b


def osm_overrides(o: gpd.GeoDataFrame, what: str) -> gpd.GeoDataFrame:
    """OSM buildings or building:parts less those [buildings] exclude.osm leaves out, with [buildings] osm_fix's
    heights for wrongly tagged ones (the height tag replaced, levels dropped). With [buildings] exclude_inside,
    whatever lies mostly (80 %) inside an outline left out by id goes with it (the London Eye's 200 rim pieces,
    mapped as building:parts inside its outline)."""
    if "osm_id" not in o:
        return o
    gone = o["osm_id"].isin(EXCLUDE_OSM)
    if B["exclude_inside"]:
        _EXCLUDED.extend(o.geometry[gone].make_valid())
        if _EXCLUDED:
            u = gpd.GeoSeries(_EXCLUDED, crs=o.crs).union_all()
            g = o.geometry.make_valid()
            near = g.intersects(u)
            inside = pd.Series(False, index=o.index)
            inside[near] = g[near].intersection(u).area >= 0.8 * g[near].area.clip(lower=1e-6)
            if (inside & ~gone).any():
                print(f"{what}: {int((inside & ~gone).sum())} inside outlines left out by id go too")
            gone |= inside
    fix = o["osm_id"].isin(OSM_FIX.keys())
    if gone.any() or fix.any():
        print(f"{what}: {int(gone.sum())} left out by id, {int(fix.sum())} heights fixed by id")
    o = o[~gone].copy()
    fix = o["osm_id"].isin(OSM_FIX.keys())
    if fix.any():
        v = o.loc[fix, "osm_id"].map(OSM_FIX)
        o.loc[fix, "height"] = v.astype(str)
        o.loc[fix, "levels"] = None
        for c in ("h_tag", "h"):
            if c in o:
                o.loc[fix, c] = v
        if "h_levels" in o:
            o.loc[fix, "h_levels"] = np.nan
    return o


def fill_shafts(rest, rh: float, geoms, hs, base) -> list:
    """[buildings] parts_fill_shafts (a ratio; 0: off): a piece of what the parts leave of a building (part_rest)
    whose outline is closed (90 % of it within 1 m) by the building's parts standing on the ground, all taller than
    it, the lowest of them parts_fill_shafts x its width (the square root of its area) or more, is a shaft between
    them, not a courtyard (Asia Square Tower 2: 393 m² at 3.5 m inside its 173-222 m parts): it takes the lowest
    surrounding part's height. Slivers (under 100 m² or 6 m wide) stay as they are. Returns [(geometry, height)]:
    the rest as it was when off."""
    if SHAFTS <= 0:
        return [(rest, rh)]
    import shapely
    out, keep = [], []
    for c in getattr(rest, "geoms", [rest]):
        if c.geom_type != "Polygon" or c.area < 100 or c.buffer(-3.0).is_empty:   # a sliver: as it was
            keep.append(c)
            continue
        near = [k for k, g in enumerate(geoms) if base[k] <= 0.5 and g.distance(c) < 1.0]
        ring = c.exterior
        if near and min(hs[k] for k in near) > rh:
            low = float(min(hs[k] for k in near))
            cov = ring.intersection(shapely.union_all([geoms[k].buffer(1.0) for k in near])).length / ring.length
            if cov >= 0.9 and low >= SHAFTS * np.sqrt(c.area):
                print(f"parts: a {c.area:.0f} m² shaft at {rh:g} m among parts of {low:g} m or more filled to it")
                out.append((c, low))
                continue
        keep.append(c)
    if keep:
        out.append((shapely.union_all(keep), rh))
    return out


def use_parts(b: gpd.GeoDataFrame, osm: gpd.GeoDataFrame | None = None) -> gpd.GeoDataFrame:
    """Replace buildings drawn in OSM as building:part outlines ([buildings] parts, 01_osm's osm_parts.gpkg)
    by their parts: a skyscraper's podium, setbacks, crown and spire, each with its own height.

    Assignment: a part belongs to the building holding most of it; an overhang (a part with a min_height,
    such as a cantilever over a neighbour) to the building of the parts it touches. A building is replaced
    when its parts cover PART_COVER of it and one of them has a height.
    Heights: the part's height tag, else its levels x level_h, else the lowest height among its siblings (never
    the building's top). A part that holds other parts is the building's outline mapped as a part too (Sky:
    building=apartments and building:part=yes at 206 m round its 206 m tower and a podium): what the others
    leave of it is the podium, at the building's own (official) height if that is lower. Such outlines are
    parts tagged building=* that hold other parts.
    Every part stands on the ground up to its top (a stack reads the same and nothing floats) except an
    overhang with nothing of its building under it, which starts at its min_height (min_h). Each keeps only
    what no taller part covers, so walls never lie in the same plane twice (flush faces flicker); slivers
    under 1.2 m wide are opened away, but a thin part rising over everything (a spire) is kept at any size.
    What the parts leave of the building (a wing, an outline drawn a little differently) stays as a piece of
    its own (h_src part_rest) at the height of an OSM building mapped there (not the tower's own outline),
    else of its lowest part."""
    f = DATA / "osm_parts.gpkg"
    if not f.exists():
        return b
    p = osm_overrides(gpd.read_file(f).to_crs(UTM), "parts")
    if B["parts_in"]:
        # only the parts of these OSM buildings (80 % inside their outlines), or these parts themselves
        ids = set(B["parts_in"])
        import pyogrio
        sel = ", ".join(f"'{i}'" for i in ids)
        o = pyogrio.read_dataframe(DATA / "osm_buildings.gpkg", where=f"osm_id IN ({sel})")
        g = p.geometry.make_valid()
        inside = pd.Series(False, index=p.index)
        if len(o):
            u = o.to_crs(UTM).geometry.make_valid().buffer(0.5).union_all()
            near = g.intersects(u)
            inside[near] = g[near].intersection(u).area >= 0.8 * g[near].area.clip(lower=1e-6)
        n0 = len(p)
        p = p[inside | p["osm_id"].isin(ids)]
        print(f"parts: parts_in keeps {len(p):,} of {n0:,} OSM building:parts ({len(o)} outlines of {len(ids)} ids)")
    layer = pd.to_numeric(p.get("layer"), errors="coerce").fillna(0)
    above = layer >= 0
    if B["surface_layers"]:             # a part with a layer under 0 tagged location=surface is above ground
        above |= p["location"].isin(SURFACE)
    if UNDERGROUND_DROP:                # [osm] underground_drop: parts of malls and stations under the street
        above &= ~underground_mask(p)
    p = p[(p["location"] != "underground") & above & p.geometry.notna()
          & ~p["part"].isin(B["osm_skip"] + ["no"])].copy()          # building:part=no: a whole outline
    p["geometry"] = p.geometry.make_valid()
    p = p[p.geom_type.isin(["Polygon", "MultiPolygon"]) & (p.area >= 0.25)].reset_index(drop=True)
    p["tagged"] = num(p["height"]).notna()
    p["ph"] = num(p["height"]).fillna(num(p["levels"]) * LEVEL_H)
    p.loc[p.ph <= 0, "ph"] = np.nan
    p["pmin"] = num(p["min_height"]).fillna(num(p["min_level"]) * LEVEL_H).fillna(0)
    # outlines mapped as parts: a part holding another part (80 % of it inside)
    pi = gpd.sjoin(p[["geometry"]].reset_index(names="o"), p[["geometry"]].reset_index(names="i"),
                   predicate="intersects")
    pi = pi[pi.o != pi.i]
    import shapely
    inter = shapely.area(shapely.intersection(p.geometry.values[pi.o.values], p.geometry.values[pi.i.values]))
    pi = pi[(inter >= 0.8 * p.area.values[pi.i.values]) & (p.area.values[pi.o.values] > p.area.values[pi.i.values])]
    # ... that is tagged as a building too (a tower's own part that holds its lower floors is no outline)
    tagged = p["building"].notna() & ~p["building"].isin(["no"])
    p["outline"] = p.index.isin(pi.o.unique()) & tagged
    # host: the building holding most of a part
    ov = gpd.overlay(p[["geometry"]].reset_index(names="ip"), b[["geometry"]].reset_index(names="ib"),
                     how="intersection", keep_geom_type=True)
    ov["a"] = ov.area
    ov = ov.sort_values("a", ascending=False).drop_duplicates("ip")
    host = pd.Series(np.nan, index=p.index)
    ok = ov.a >= 0.5 * p.area.loc[ov.ip].values
    host.loc[ov.ip[ok].values] = ov.ib[ok].values
    # overhangs: the host of the grounded parts they touch
    over = p.index[p.pmin > 0.5]
    if len(over):
        tj = gpd.sjoin(p.loc[over, ["geometry"]].buffer(0.5).to_frame("geometry").set_geometry("geometry")
                       .reset_index(names="o"), p.loc[p.pmin <= 0.5, ["geometry"]].reset_index(names="g"),
                       predicate="intersects")
        tj["h"] = host.reindex(tj.g).values
        tj = tj.dropna(subset=["h"])
        if B.get("overhang_keep", 0) > 0:
            # an overhang lying overhang_keep or more inside the building that holds most of it stays with it
            # (One Blackfriars' bulging middle floors grazing the hotel next door, whose grounded parts they touch
            # three times to their own tower's two: the tower lost its middle, the hotel grew needles)
            share = pd.Series(ov.a.values / p.area.loc[ov.ip].values, index=ov.ip.values)
            tj = tj[~(share.reindex(tj.o).fillna(0).values >= B["overhang_keep"])]
        if len(tj):
            best = tj.groupby("o").h.agg(lambda v: v.value_counts().index[0])
            host.loc[best.index] = best.values
    p["host"] = host
    p = p[p.host.notna()]
    p = p[p.area <= 1.5 * b.area.reindex(p.host).values]
    cover = p.assign(a=p.area.clip(upper=b.area.reindex(p.host).values)).groupby("host").a.sum() \
        / b.area.reindex(p.groupby("host").size().index)
    has_h = p.groupby("host").ph.apply(lambda v: v.notna().any())
    hosts = cover[(cover >= PART_COVER) & has_h.reindex(cover.index).fillna(False)].index
    prim = next((f"h_{n}" for n in FOOTPRINTS if n != "osm" and f"h_{n}" in b), None)
    rows, stale = [], []
    for ib, parts in p[p.host.isin(hosts)].groupby("host"):
        hb = b.loc[ib]
        hs = parts["ph"].values.astype(float)
        known = hs[np.isfinite(hs)]
        own = hb.get(prim) if prim else np.nan
        # a part without a height: the lowest of its siblings' if they differ; with one known height (the
        # tower's) it is the podium: the building's own height or its floors if lower, at most 5 storeys
        if len(np.unique(known)) >= 2:
            fill = known.min()
        else:
            cands = [known.min(), 5 * LEVEL_H] + ([own] if pd.notna(own) and own > 0 else [])
            nf = hb.get("numfloors")
            if pd.notna(nf) and nf > 0:
                cands.append(nf * LEVEL_H)
            fill = min(cands)
        hs = np.where(np.isfinite(hs), hs, fill)
        if pd.notna(own) and own > known.max() + max(20, 0.3 * known.max()):
            stale.append(ib)          # parts of what stood there before (25 Park Row): the building stays whole
            continue
        # a part without a height tag (its levels x level_h, a sibling's height) far under the height the
        # official layer measured over the building (APUR's median, h_med) is too low: Saint-Lazare's train shed
        # at 3.5 m for 15, the Hôtel de Ville at 16.5 for 28; a large one (300 m² or a fifth of the building) is
        # floored at 0.8 of it
        ref = pd.to_numeric(hb.get("h_med"), errors="coerce") if "h_med" in hb else np.nan
        if pd.notna(ref) and ref > 0:
            big = (parts.area.values >= 300) | (parts.area.values >= 0.2 * hb.geometry.area)
            low = ~parts.tagged.values & big & (hs < 0.6 * ref)
            hs = np.where(low, 0.8 * ref, hs)
        top = hs.max()
        for k in np.flatnonzero(parts.outline.values):
            # an outline's own area is the podium: the building's own height if that is lower
            inner = hs[[j for j in range(len(parts)) if j != k and
                        parts.geometry.iloc[j].intersection(parts.geometry.iloc[k]).area >= 0.8 * parts.geometry.iloc[j].area]]
            cand = [hs[k]] + ([own] if pd.notna(own) and own > 0 else []) + list(inner)
            hs[k] = min(cand)
        # an overhang: a part starting up in the air with less than half of it over lower parts of its building
        pm = parts.pmin.values
        # (over the building's own footprint a part stands on its floors, mapped or not: only what reaches
        # out over a neighbour or a street floats)
        # With [buildings] lift_parts, a raised part over its own footprint keeps its min_height too when mapped
        # parts meet its underside or when it is no thicker than the gap below it (see below); a tower's setback
        # (min 30 m, top 200 m) with nothing mapped under it still stands on its unmapped floors
        overhangs = set()
        inside = set()
        gaps = set()                               # lift_parts = "gaps": lifted over the building's own body
        h0 = float(hb["h"]) if pd.notna(hb.get("h")) else 0.0
        # (the building's own top for lift_parts = "gaps": its height, or OSM's tags on its outline if higher:
        # Pinnacle@Duxton's blocks at HDB's 144 m from storeys, tagged 150 m)
        h_own = max([h0] + [float(v) for v in (hb.get("h_osm_tag"), hb.get("h_osm_levels")) if pd.notna(v)])
        grounded = [parts.geometry.iloc[j] for j in range(len(parts)) if pm[j] <= 0.5]
        grounded = shapely.union_all(grounded) if grounded else None
        g_top = max([hs[j] for j in range(len(parts)) if pm[j] <= 0.5], default=0.0)
        for k in np.flatnonzero(pm > 0.5):
            gk = parts.geometry.iloc[k]
            within = gk.intersection(hb.geometry).area >= 0.5 * gk.area
            if within and LIFT:
                # it stands on mapped parts whose tops meet its underside (the Arc de Triomphe's attic on its
                # piers and arch tops: what is between them stays open), or it is a slab or span no thicker
                # than the gap under it (the Grande Arche's roof, the arches' tops, a viaduct's station)
                sup = [parts.geometry.iloc[j] for j in range(len(parts))
                       if j != k and pm[k] - 1 <= hs[j] <= pm[k] + 0.5]
                on = shapely.union_all(sup) if sup else None
                supported = on is not None and gk.intersection(on).area >= 0.5 * gk.area
                thin = hs[k] - pm[k] <= pm[k] + 0.5
                if LIFT_GAPS:
                    # only a slab or span over a real gap in a low building: no grounded part of the building
                    # mapped under it (MBS's expo roofs over their hall), none rising to its underside anywhere (a
                    # tower whose crown, sky gardens or core segments are mapped from a min_height: OCBC Centre,
                    # South Beach, ION Orchard), not on mapped parts reaching it, not under the building's own top
                    # (its height or height tags reaching the underside: the floors are there, unmapped), and not
                    # the top of the building itself (half its footprint or more). Under it the building's own
                    # body stays, at h0 (the National Stadium's seating bowl under its roof rings; Pinnacle@Duxton's
                    # podium under the skybridges), so its height must be known (not the default: ION Orchard's mall
                    # under its crown)
                    on_ground = grounded is not None and gk.intersection(grounded).area >= 0.05 * gk.area
                    if (not supported and not on_ground and g_top < pm[k] - 1 and thin and h_own < pm[k] - 1
                            and hb.get("h_src") not in (None, "default")
                            and gk.intersection(hb.geometry).area < 0.5 * hb.geometry.area):
                        overhangs.add(k)
                        inside.add(k)
                        gaps.add(k)
                    continue
                if supported or thin:
                    overhangs.add(k)
                    inside.add(k)
                continue
            if within:
                continue
            lower = [parts.geometry.iloc[j] for j in range(len(parts)) if j != k and pm[j] < pm[k]]
            under = shapely.union_all(lower) if lower else None
            if under is None or gk.intersection(under).area < 0.5 * gk.area:
                overhangs.add(k)
        # tallest first; of equal tops the one reaching lowest first (a stack of slabs hung from one roof)
        base = np.where([k in overhangs for k in range(len(parts))], pm, 0.0)
        order = np.lexsort((base, -hs))
        taken = None
        done = []                                  # (geometry, base) of the parts placed so far
        for k in order:
            part = parts.iloc[k]
            overhang = k in overhangs
            g = part.geometry if overhang and k not in inside else part.geometry.intersection(hb.geometry.buffer(0.5))
            # only what a taller part covers at the same heights is taken away: a part under a lifted slab keeps
            # its whole footprint up to the slab's underside
            over = [dg for dg, base in done if base < hs[k] - 0.5]
            if over:
                g = g.difference(shapely.union_all(over))
                if g.area > 30:
                    # slivers left where a lower part is drawn a little wider than the one above: gone
                    g = g.buffer(-0.6, join_style=2).buffer(0.6, join_style=2)
            done.append((part.geometry, part.pmin if overhang else 0.0))
            if k not in gaps:                      # (under a lifted span the building's body stays: below)
                taken = part.geometry if taken is None else taken.union(part.geometry)
            spire = hs[k] >= top - 5
            if g.is_empty or (g.area < MIN_PIECE and not spire):
                continue
            rows.append({**hb.drop("geometry").to_dict(), "h": hs[k], "min_h": part.pmin if overhang else 0.0,
                         "h_src": "osm_part" if pd.notna(part.ph) else "osm_part_sibling",
                         "part_of": ib, "geometry": g})
        # what the parts leave of the building: at the height of an OSM building mapped there (not the
        # tower's own outline), else of its lowest part
        rest = (hb.geometry.difference(taken) if taken is not None else hb.geometry) \
            .buffer(-1.5, join_style=2).buffer(1.5, join_style=2)
        body, body_h = None, h0
        if gaps:
            # the body under spans lifted over a gap (lift_parts = "gaps"): at the height of the rest of the building
            # (below), else its own height, at most their lowest underside
            span = shapely.union_all([parts.geometry.iloc[k] for k in gaps])
            body = rest.intersection(span)
            rest = rest.difference(span)
        if not rest.is_empty and rest.area >= 30 and rest.area >= 0.05 * hb.geometry.area:
            rh = hs.min() if len(np.unique(hs)) >= 2 else min(fill, hs.min())
            if osm is not None:
                o = osm[(osm["h"].notna() | osm["h_levels"].notna()) & osm.intersects(rest)]
                if len(o):
                    share = o.intersection(rest).area / rest.area
                    inside = o.intersection(rest).area / o.area
                    good = (share >= 0.5) | (inside >= 0.5)
                    if good.any():
                        k = share[good].idxmax()
                        oh = o.at[k, "h"] if pd.notna(o.at[k, "h"]) else o.at[k, "h_levels"]
                        if oh < hs.max() - 5:                # not the tower's own outline
                            rh = float(oh)
            if pd.notna(ref) and ref > 0 and rest.area >= 300 and rh < 0.6 * ref:
                rh = 0.8 * ref
            for g, h in fill_shafts(rest, rh, parts.geometry.values, hs, base):
                rows.append({**hb.drop("geometry").to_dict(), "h": h, "min_h": 0.0, "h_src": "part_rest",
                             "part_of": ib, "geometry": g})
            body_h = rh
        if body is not None:
            body_h = min(body_h, float(min(pm[k] for k in gaps)))
            if not body.is_empty and body.area >= MIN_PIECE and body_h >= MIN_H:
                rows.append({**hb.drop("geometry").to_dict(), "h": body_h, "min_h": 0.0, "h_src": "part_rest",
                             "part_of": ib, "geometry": body})
    if not rows:
        return b
    parts_b = gpd.GeoDataFrame(rows, crs=UTM)
    parts_b = parts_b[parts_b.geom_type.isin(["Polygon", "MultiPolygon"])]
    hosts = hosts.difference(stale)
    if stale:
        print(f"parts: {len(stale)} buildings keep their outline, their parts being far lower (older)")
    out = gpd.GeoDataFrame(pd.concat([b.drop(index=hosts), parts_b], ignore_index=True), crs=UTM)
    print(f"parts: {len(hosts):,} buildings made of {len(parts_b):,} OSM building parts "
          f"({int(p.outline.sum()):,} parts are outlines holding others; "
          f"{int((parts_b.min_h > 0).sum()):,} overhangs)")
    return out


SPIKES = B["spikes"]


def despike(b: gpd.GeoDataFrame, osm: gpd.GeoDataFrame | None = None) -> gpd.GeoDataFrame:
    """[buildings.spikes]: a height source that gives each polygon its highest point (Carbon & Place's lidar
    maximum) also gives a low building the chimney on it, its rooftop plant or the edge of the tower beside it
    (London: the West Wintergarden 152 m for 25, Cabot Place 134 for 23). Where such a source set the height
    (h_src one of `sources`), the top is a spike when the polygon's mean height (h_mean, [sources.<name>] mean)
    is under `mean_share` of it (a flat roof at its top has a mean near it; no mean known: no test) and
      1. OSM says much lower: its height tag (from an OSM building that is mostly this footprint), else its
         levels x level_h + `roof` m (of the OSM building this footprint is, IoU 0.5, however large: the O2's 50 m
         under its masts' 89), the top is over max(that + `over`, `ratio` x that); or
      2. OSM says nothing, but a touching footprint (within 1 m) has the same top (`near` of it or more, from
         `min_h` m) and is solid there (its own mean at least `mean_share` of its top): the top is that
         neighbour's, caught at the polygon's edge; tested only where the mean is under `neighbour_share`.
    The height becomes OSM's (1) or the mean x `mean_scale` (2), and never less than the mean x `mean_scale`
    (an OSM tag of 2.5 m on a 25 m hotel) nor more than the top; h_src "<source>~osm" or "<source>~mean"."""
    if not SPIKES or not SPIKES.get("sources"):
        return b
    n0 = {}
    for src in SPIKES["sources"]:
        hc, mc = f"h_{src}", f"hmean_{src}"
        if hc not in b:
            continue
        top = b[hc]
        mean = b[mc] if mc in b else pd.Series(np.nan, index=b.index)
        est = (mean * SPIKES["mean_scale"]).where(mean > 0)
        mine = b.h_src.eq(src) & top.notna()
        low_mean = mean.isna() | (mean < SPIKES["mean_share"] * top)
        tag = b["h_osm_tag"].where(b.get("osm_share", pd.Series(1.0, index=b.index)) >= 0.5) \
            if "h_osm_tag" in b else pd.Series(np.nan, index=b.index)
        lev = b["h_osm_levels"] + SPIKES["roof"] if "h_osm_levels" in b else pd.Series(np.nan, index=b.index)
        if osm is not None and "osm_id" in b:          # the OSM building this footprint is, at any size
            by_id = osm.drop_duplicates("osm_id").set_index("osm_id")
            tag = tag.fillna(b["osm_id"].map(by_id["h_tag"]))
            lev = lev.fillna(b["osm_id"].map(by_id["h_levels"]) + SPIKES["roof"])
        osm_h = tag.where(tag > 0).fillna(lev.where(lev > SPIKES["roof"]))
        r1 = mine & low_mean & osm_h.notna() & (top > np.maximum(osm_h + SPIKES["over"], SPIKES["ratio"] * osm_h))
        # 2. a neighbour's top at the polygon's edge
        cand = b.index[mine & osm_h.isna() & (top >= SPIKES["min_h"]) & mean.notna()
                       & (mean < SPIKES["neighbour_share"] * top)]
        r2 = pd.Series(False, index=b.index)
        if len(cand):
            solid = top.notna() & (mean.isna() | (mean >= SPIKES["mean_share"] * top))
            nb = b.loc[solid, ["geometry"]].assign(t=top[solid])
            j = gpd.sjoin(b.loc[cand, ["geometry"]].assign(geometry=b.loc[cand].geometry.buffer(1.0)), nb,
                          predicate="intersects")
            j = j[(j.index != j.index_right) & (j.t >= SPIKES["near"] * top.reindex(j.index).values)]
            r2.loc[j.index.unique()] = True
        new = osm_h.where(r1, est.where(r2))
        new = np.maximum(new, est.fillna(0)).clip(upper=top)
        # 3. (alone_ratio > 0) no OSM height tag and no neighbour to explain it: a top alone far over the mean
        #    (over alone_ratio x it: a church's steeple, floodlights, the Barbican Conservatory's fly tower
        #    neighbour), or over a mean under alone_mean m (a building site in the lidar, a crane), from
        #    alone_min_h m: OSM's levels x level_h + roof m if any, else the mean x mean_scale (x body_scale for
        #    body_tags: a church's nave, its spire left to the landmark pass), else (a site) the default height
        r3 = pd.Series(False, index=b.index)
        if SPIKES.get("alone_ratio", 0):
            tag_ok = tag.where(tag > 0)
            r3 = (mine & ~r1 & ~r2 & tag_ok.isna() & mean.notna() & (top >= SPIKES["alone_min_h"])
                  & ((top > SPIKES["alone_ratio"] * mean) | (mean < SPIKES["alone_mean"])))
            scale = pd.Series(SPIKES["mean_scale"], index=b.index)
            if "osm_building" in b:
                scale[b["osm_building"].isin(SPIKES.get("body_tags", []))] = SPIKES.get("body_scale", SPIKES["mean_scale"])
            v3 = lev.where(lev > SPIKES["roof"]).fillna(
                (mean * scale).where(mean >= SPIKES["alone_mean"], B["default_floors"] * LEVEL_H))
            new = new.where(~r3, v3.clip(upper=top))
        ok = (r1 | r2 | r3) & new.notna() & (new < top - 1)
        b.loc[ok, "h"] = new[ok]
        b.loc[ok & r1, "h_src"] = f"{src}~osm"
        b.loc[ok & r2 & ~r1, "h_src"] = f"{src}~mean"
        b.loc[ok & r3, "h_src"] = f"{src}~alone"
        n0[src] = (int((ok & r1).sum()), int((ok & r2 & ~r1).sum()), int((ok & r3).sum()))
        b[f"spike_{src}"] = top.where(ok)                 # the source's top that was taken for a spike
    for src, (a, c, d) in n0.items():
        print(f"spikes: {src}: {a:,} tops far over OSM's height or levels, {c:,} a touching building's top "
              f"(lowered to OSM's or the mean x {SPIKES['mean_scale']}), {d:,} alone over their mean")
    # caps: an OSM building tag's highest height without an OSM height tag (a stand's floodlights)
    caps = SPIKES.get("caps", {})
    if caps and "osm_building" in b:
        cap = b["osm_building"].map(caps)
        tagged = b["h_osm_tag"].notna() if "h_osm_tag" in b else pd.Series(False, index=b.index)
        over = cap.notna() & ~tagged & (b["h"] > cap)
        b.loc[over, "h"] = cap[over]
        b.loc[over, "h_src"] = b.loc[over, "h_src"].astype(str) + "~cap"
        print(f"spikes: {int(over.sum())} buildings capped by their OSM tag ({', '.join(f'{k} {v:g} m' for k, v in caps.items())})")
    return b


def split_podiums(b: gpd.GeoDataFrame, heights: dict) -> gpd.GeoDataFrame:
    """[buildings.spikes] podium = {area, ratio, min_h} ({}: off): a large footprint (area m² or more) whose
    top from a lidar-maximum source is over ratio x its mean and min_h m, with no OSM height tag, is one block
    holding buildings of different heights (a station and the office over it, a hotel's tower on its podium)
    extruded whole to the tallest. Where the source's polygons under it are two or more and cover half of it, it
    is split along them, each piece at its polygon's top (or the polygon's mean x mean_scale where that mean is
    under mean_share of its top), the rest at the footprint's mean x mean_scale (h_src "<source>~split");
    otherwise the whole takes the mean x mean_scale, or OSM's levels x level_h + roof m if higher
    ("<source>~podium")."""
    pod = SPIKES.get("podium", {}) if SPIKES else {}
    if not pod:
        return b
    rows, drop, n_split, n_flat = [], [], 0, 0
    for src in SPIKES["sources"]:
        hc, mc = f"h_{src}", f"hmean_{src}"
        if hc not in b or mc not in b or src not in heights:
            continue
        g = heights[src]
        tagged = b["h_osm_tag"].notna() if "h_osm_tag" in b else pd.Series(False, index=b.index)
        top, mean = b[hc], b[mc]
        solid = b["part_of"].isna() if "part_of" in b else pd.Series(True, index=b.index)
        cand = b.index[b.h_src.eq(src) & ~tagged & solid & (b.area >= pod["area"]) & (top > pod["ratio"] * mean)
                       & (top > pod["min_h"])]
        if not len(cand):
            continue
        ov = gpd.overlay(b.loc[cand, ["geometry"]].reset_index(names="ib"),
                         g[["geometry", "h"] + (["h_mean"] if "h_mean" in g else [])].reset_index(names="ig"),
                         how="intersection", keep_geom_type=True)
        ov = ov[ov.area >= 50]
        for i in cand:
            r = b.loc[i]
            pcs = ov[ov.ib == i]
            est = float(r[mc]) * SPIKES["mean_scale"]
            if len(pcs) >= 2 and pcs.area.sum() >= 0.5 * r.geometry.area and pcs.h.nunique() >= 2:
                drop.append(i)
                for pc in pcs.itertuples():
                    pm = getattr(pc, "h_mean", np.nan)
                    ph = pc.h if not (pd.notna(pm) and pm < SPIKES["mean_share"] * pc.h) else pm * SPIKES["mean_scale"]
                    rows.append({**r.drop("geometry").to_dict(), "h": max(float(ph), MIN_H),
                                 "h_src": f"{src}~split", "geometry": pc.geometry})
                rest = r.geometry.difference(pcs.geometry.union_all()).buffer(-1, join_style=2).buffer(1, join_style=2)
                if not rest.is_empty and rest.area >= MIN_PIECE:
                    rows.append({**r.drop("geometry").to_dict(), "h": max(est, MIN_H), "h_src": f"{src}~split",
                                 "geometry": rest})
                n_split += 1
            else:
                lv = r.get("h_osm_levels")
                h = max(est, float(lv) + SPIKES["roof"] if pd.notna(lv) else 0.0, MIN_H)
                if h < r["h"] - 1:
                    b.at[i, "h"], b.at[i, "h_src"] = h, f"{src}~podium"
                    n_flat += 1
    print(f"podiums: {n_split} large footprints split along their height source's polygons, {n_flat} lowered to "
          f"their mean x {SPIKES['mean_scale']} (or OSM's levels)")
    if not rows:
        return b
    return gpd.GeoDataFrame(pd.concat([b.drop(index=drop), gpd.GeoDataFrame(rows, crs=UTM)], ignore_index=True),
                            crs=UTM)


def landmark_podiums(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """[buildings.landmarks] podium = {ratio, base, area} ({}: off): a landmark tower (a use_height row of the
    list, a building) whose point lies on a plain footprint (no OSM parts) that also holds its podium would give
    the listed height to the whole block (Hilton Park Lane's 101 m over its whole 4,700 m² site; One Thames City's
    two towers on one 8,750 m² outline). Where the lidar-maximum source ([buildings.spikes] sources) says so (its
    top over `ratio` x the footprint's mean, the footprint `area` m² or more), the tower is cut out as a box at
    its point: oriented with the footprint's minimum rotated rectangle and of its proportions (at most 2:1), of the
    area that keeps the source's volume (mean x area = podium x the rest + listed x the towers'), pulled towards
    the footprint's middle until it lies in it. The rest is the podium: OSM's levels x level_h where that is under
    half the mean, else `base` m (h_src "landmark~podium"). Several towers on one footprint each get a box. An OSM
    building:part under the point (lying in the footprint, without a height, so use_parts left it) is the tower's
    own outline and is taken instead of a box (One Thames City's "No. 8" and "No. 9")."""
    pod = LM.get("podium", {})
    if not pod or not LANDMARKS or not SPIKES or not SPIKES.get("sources"):
        return b
    src = SPIKES["sources"][0]
    hc, mc = f"h_{src}", f"hmean_{src}"
    if hc not in b or mc not in b:
        return b
    lm = pd.concat([pd.read_csv(f) for f in LANDMARKS], ignore_index=True)
    lm = lm[lm["use_height"].astype(str).str.lower().eq("true")
            & lm.get("feature", pd.Series("building", index=lm.index)).fillna("building").eq("building")]
    lm = lm.dropna(subset=["lat", "lon", "height_m"])
    if not len(lm):
        return b
    pts = gpd.GeoDataFrame(lm, geometry=[Point(xy) for xy in zip(lm.lon, lm.lat)], crs="EPSG:4326").to_crs(UTM)
    solid = b["part_of"].isna() if "part_of" in b else pd.Series(True, index=b.index)
    j = gpd.sjoin(pts[["geometry", "height_m", "name_zh"]], b.loc[solid, ["geometry"]], predicate="within")
    f = DATA / "osm_parts.gpkg"
    op = gpd.read_file(f).to_crs(UTM)[["geometry"]] if f.exists() else None
    if op is not None:
        op = op[op.geom_type.isin(["Polygon", "MultiPolygon"])]
        op = op.assign(geometry=op.geometry.make_valid())
    rows, drop = [], []
    for k, grp in j.groupby("index_right"):
        r = b.loc[k]
        g, top, mean = r.geometry, r[hc], r[mc]
        area = g.area
        if not (pd.notna(top) and pd.notna(mean) and mean > 0 and area >= pod.get("area", 1000.0)
                and top >= pod["ratio"] * mean):
            continue
        lv = r.get("h_osm_levels")
        hp = float(lv) if pd.notna(lv) and 0 < lv < 0.5 * mean else float(pod["base"])
        listed = grp.height_m.values.astype(float)
        # the tallest listed tower must be what the lidar's top saw (not the O2's masts over its 52 m dome)
        if (listed <= hp + 10).any() or mean <= hp or listed.max() < pod.get("top_share", 0.85) * top:
            continue
        a = area * (mean - hp) / (listed - hp).sum()
        a = float(np.clip(a, 0.08 * area, 0.85 * area / len(grp)))
        rr = np.asarray(g.minimum_rotated_rectangle.exterior.coords)
        e1, e2 = rr[1] - rr[0], rr[2] - rr[1]
        if np.linalg.norm(e1) < np.linalg.norm(e2):
            e1, e2 = e2, e1
        aspect = min(np.linalg.norm(e1) / max(np.linalg.norm(e2), 1e-6), 2.0)
        u, v = e1 / np.linalg.norm(e1), e2 / max(np.linalg.norm(e2), 1e-9)
        L, W = np.sqrt(a * aspect), np.sqrt(a / aspect)
        cen = np.array(g.centroid.coords[0])
        taken = None
        boxes = []
        for p, hl, name in zip(grp.geometry, listed, grp.name_zh):
            c0 = np.array(p.coords[0])
            best = None
            if op is not None:
                own = op[op.contains(p)]
                own = own[(own.intersection(g).area >= 0.8 * own.area) & (own.area >= 150) & (own.area <= 0.85 * area)]
                if len(own):
                    best = own.geometry.loc[own.area.idxmin()].intersection(g)
                    if taken is not None:
                        best = best.difference(taken)
            for t in (np.linspace(0, 1, 11) if best is None else []):   # from the point towards the middle
                c = c0 + (cen - c0) * t
                box = Polygon([c + sx * u * L / 2 + sy * v * W / 2 for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
                piece = box.intersection(g)
                if taken is not None:
                    piece = piece.difference(taken)
                if best is None or piece.area > best.area + 1:
                    best = piece
                if piece.area >= 0.9 * a:
                    break
            if best is None or best.is_empty or best.area < 0.3 * a:
                continue
            taken = best if taken is None else taken.union(best)
            boxes.append((best, hl, name))
        if not boxes:
            continue
        drop.append(k)
        for piece, hl, name in boxes:
            rows.append({**r.drop("geometry").to_dict(), "h": float(top), "h_src": f"{src}~tower", "geometry": piece})
            print(f"landmark podiums: {name}: a {piece.area:,.0f} m² tower cut from its {area:,.0f} m² footprint "
                  f"(top {top:.0f} m, mean {mean:.1f}), the rest at {hp:.1f} m")
        rest = g.difference(taken).buffer(-1, join_style=2).buffer(1, join_style=2)
        if not rest.is_empty and rest.area >= MIN_PIECE:
            rows.append({**r.drop("geometry").to_dict(), "h": max(hp, MIN_H), "h_src": "landmark~podium",
                         "geometry": rest})
    if not rows:
        return b
    return gpd.GeoDataFrame(pd.concat([b.drop(index=drop), gpd.GeoDataFrame(rows, crs=UTM)], ignore_index=True),
                            crs=UTM)


RECONCILE = B["reconcile"]


def reconcile(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Second opinions ([buildings] reconcile): a height source listed there replaces the chosen height where
    it is taller by more than max(over m, share x the chosen height), OSM's only where the OSM building is
    mostly this footprint (half of it or more) (a cadastre can keep a demolished
    building's roof, or a tower's while it was going up: Manhattan's 270 Park Avenue at 213 m for 423 m),
    and wherever the chosen height is under `flat` m on a footprint over 300 m² (a pancake). Such buildings
    get h_src "<source>+" ."""
    if not RECONCILE or not RECONCILE["sources"]:
        return b
    col = {"osm_height": "h_osm_tag", "osm_levels": "h_osm_levels"}
    floors = pd.to_numeric(b.get("numfloors"), errors="coerce") if "numfloors" in b else None
    n = 0
    for src in RECONCILE["sources"]:
        v = b[col.get(src, f"h_{src}")]
        # only from an OSM building that is mostly this one (not a small older building inside a tower's outline)
        if src.startswith("osm") and "osm_share" in b:
            v = v.where(b["osm_share"] >= 0.5)
        if floors is not None:          # no more than the floors can hold
            v = v.where(floors.isna() | (floors <= 0) | (v <= floors * 4.5 + 15))
        up = v.notna() & (v > b.h + np.maximum(RECONCILE["over"], RECONCILE["share"] * b.h))
        flat = v.notna() & (b.h < RECONCILE["flat"]) & (b.area > 300) & (v > b.h)
        ok = (up | flat) & (b.h_src != src)
        b.loc[ok, "h"] = v[ok]
        b.loc[ok, "h_src"] = src + "+"
        n += int(ok.sum())
        # and down, for big blocks: a department store or hospital complex given its tallest wing's roof
        # (Macy's 12,400 m² at 98 m; OSM 51) where OSM's building is mostly this one
        if src.startswith("osm"):
            down = v.notna() & (b.area >= RECONCILE["big"]) & (v < 0.6 * b.h) & (b.h_src != src)
            b.loc[down, "h"] = v[down]
            b.loc[down, "h_src"] = src + "-"
            n += int(down.sum())
    print(f"reconcile: {n:,} heights raised by a second source")
    return b


CANTILEVER = B["cantilever_code"]


def cantilevers(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """A cantilevered footprint ([buildings] cantilever_code in the source's feature_code: NYC's 1006) reaches
    over its neighbours: the part of it over another building starts at that building's roof (min_h), the
    rest stands on the ground."""
    if "feature_code" not in b or CANTILEVER is None:
        return b
    part_of = b.get("part_of", pd.Series(np.nan, index=b.index))
    cant = b.index[(b["feature_code"] == CANTILEVER) & part_of.isna()]
    rows, drop = [], []
    others = b.drop(index=cant)
    built = set(b.loc[part_of.notna(), "bin"].dropna()) if "bin" in b else set()
    for i in cant:
        r = b.loc[i]
        if r.get("bin") in built:        # a piece of a building already made of its parts (cantilever included)
            drop.append(i)
            continue
        under = others[others.intersects(r.geometry)]
        if "bin" in b:
            under = under[under["bin"] != r.get("bin")]
        under = under[under.intersection(r.geometry).area >= 5]
        if not len(under):
            continue
        over = r.geometry.intersection(under.geometry.union_all())
        low = float(under.h.max())
        if over.area < 0.05 * r.geometry.area or low >= r.h - MIN_H:
            continue                     # hardly over anything, or over something as tall: stands on the ground
        drop.append(i)
        rows.append({**r.drop("geometry").to_dict(), "min_h": low, "geometry": over})
        rest = r.geometry.difference(over)
        if rest.area >= MIN_PIECE:
            rows.append({**r.drop("geometry").to_dict(), "geometry": rest})
    if not rows:
        return b
    print(f"cantilevers: {len(drop):,} footprints reach over {len(drop):,}+ neighbours: overhangs lifted")
    return gpd.GeoDataFrame(pd.concat([b.drop(index=drop), gpd.GeoDataFrame(rows, crs=UTM)], ignore_index=True),
                            crs=UTM)


def copied(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """A tower's roof height copied onto a small building beside it (a cadastre gives the whole lot one
    height: 432 Park Avenue's 425 m on the 90 m² building at its foot): a footprint under half the size of
    a touching one with the same height (within a metre, 60 m or more) takes OSM's height where OSM's
    building is mostly this one, else the median height of its other neighbours."""
    tall = b[(b.h >= 60) & (b.h_src != "landmark")]
    if not len(tall):
        return b
    j = gpd.sjoin(tall[["geometry", "h"]].reset_index(names="i"), b[["geometry", "h"]].reset_index(names="k"),
                  predicate="intersects")
    j = j[(j.i != j.k) & ((j.h_left - j.h_right).abs() <= 1.0)]
    j = j[b.area.reindex(j.i).values < 0.5 * b.area.reindex(j.k).values]
    # the same tax lot (a lot's height handed to each of its buildings), where lots are known
    lot = next((c for c in ("mappluto_bbl", "base_bbl", "bbl") if c in b), None)
    if lot:
        j = j[(b[lot].reindex(j.i).values == b[lot].reindex(j.k).values)]
    if "numfloors" in b:                          # 30 floors carry 90 m: no copy
        nf = pd.to_numeric(b["numfloors"], errors="coerce").reindex(j.i).fillna(0).values
        j = j[nf * 3 < 0.8 * j.h_left.values]
    fixed, confirmed = 0, 0
    keep_src = [f"h_{s}" for s in B["copied_keep"] if f"h_{s}" in b]
    for i in j.i.unique():
        # [buildings] copied_keep: a second source measuring the same height on this piece (the Umweltatlas's
        # laser on a tower's own parts) says it is the tower's, not a copy
        hi = b.at[i, "h"]
        if any(pd.notna(b.at[i, c]) and abs(b.at[i, c] - hi) <= max(5.0, 0.1 * hi) for c in keep_src):
            confirmed += 1
            continue
        # [buildings] copied_storeys: where none of them has a height, storeys that can carry it (5 m each) do
        st = B["copied_storeys"]
        if keep_src and st and st in b and all(pd.isna(b.at[i, c]) for c in keep_src):
            n = pd.to_numeric(b.at[i, st], errors="coerce")
            if pd.notna(n) and n > 0 and hi <= 5.0 * n:
                confirmed += 1
                continue
        osm_h = b.at[i, "h_osm_tag"] if b.at[i, "osm_share"] >= 0.5 else np.nan
        nf = pd.to_numeric(b.at[i, "numfloors"], errors="coerce") if "numfloors" in b else np.nan
        if pd.notna(osm_h) and pd.notna(nf) and nf > 0 and not (nf * 1.5 <= osm_h <= nf * 6):
            osm_h = np.nan                        # OSM's height disagrees with the lot's floors
        if pd.notna(osm_h) and osm_h < b.at[i, "h"] - 20:
            h = osm_h
        else:
            nb = b[b.intersects(b.geometry[i].buffer(1)) & ((b.h - b.at[i, "h"]).abs() > 1.0)]
            if not len(nb):
                continue
            h = float(nb.h.median())
        if h < b.at[i, "h"] - 20:
            b.at[i, "h"], b.at[i, "h_src"] = h, "copied_fix"
            fixed += 1
    print(f"copied: {fixed:,} small buildings carried a touching tower's height"
          + (f" ({confirmed:,} more left as they are: {', '.join(B['copied_keep'])} measures the same)" if keep_src else ""))
    return b


def nested(b: gpd.GeoDataFrame) -> pd.Series:
    """Height a building starts at above the ground (min_h): a footprint lying mostly (90 %) inside a taller
    one stands on its roof (Manhattan: the park buildings on the North River treatment plant); otherwise 0."""
    j = gpd.sjoin(b[["geometry", "h"]].reset_index(names="i"), b[["geometry", "h"]].reset_index(names="k"),
                  predicate="intersects")
    j = j[(j.i != j.k) & (j.h_right > j.h_left)]
    # never on a tower's part or on a cantilevered footprint (whose overhang is not a roof to stand on)
    solid = pd.Series(True, index=b.index)
    if "part_of" in b:
        solid &= b["part_of"].isna()
    if "feature_code" in b:
        solid &= b["feature_code"] != CANTILEVER
    if "osm_deck" in b:                 # [osm] min_height: a deck is no roof to stand on (what lies in it is under it)
        solid &= ~b["osm_deck"].fillna(False).astype(bool)
    j = j[solid.reindex(j.k).values & solid.reindex(j.i).values]
    own = own_ground(b)                 # [buildings] own_ground: a piece on its own measured ground is never nested
    j = j[~own.reindex(j.i).values]
    out = pd.Series(0.0, index=b.index)
    if not len(j):
        return out
    import shapely
    geo = pd.Series(shapely.make_valid(b.geometry.values), index=b.index)
    inter = shapely.area(shapely.intersection(geo.loc[j.i].values, geo.loc[j.k].values))
    j = j[inter >= 0.9 * b.area.loc[j.i].values]
    top = j.groupby("i").h_right.max()
    out.loc[top.index] = top.values
    return out


def own_ground(b: gpd.GeoDataFrame) -> pd.Series:
    """[buildings] own_ground: the pieces whose source measured their own ground and roof (ground_elevation and
    roof_top_z: a cadastre's LoD2 solids). They stand on their ground and reach roof_top_z - ground_elevation; a
    canopy lying over a hall, or a twin solid drawn over another, is not their podium."""
    if not B["own_ground"] or "ground_elevation" not in b or "roof_top_z" not in b:
        return pd.Series(False, index=b.index)
    return (pd.to_numeric(b["ground_elevation"], errors="coerce").notna()
            & pd.to_numeric(b["roof_top_z"], errors="coerce").notna())


RECHECK = B["recheck"]


def recheck(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """[buildings] recheck ({}: off): a second height source with the same footprints (`source`: Berlin's
    Umweltatlas, h_<source>) over the heights of `of` (h_src: the LoD2's laser) where these are placeholders or
    generalised solids. 1. low: at `low` m or less where the second source is over `ratio` x higher (the LoD2's
    roofType 9999 solids at a placeholder 3-3.5 m: the Abgeordnetenhaus 3.5 m for 27, the Moabit court 24.9).
    2. gen: pieces whose `field` is one of `values` (roofType 9999, generalised: one flat top for a whole complex)
    more than `diff` m off the second source (the BND's 41,800 m² at 13.1 m for 33.3; the Dom's body at its cornice
    43.4 for 33.7); a lower second height only where it is closer to the storeys (`storeys` field x `storey_h`).
    Pieces with their own exact height ([buildings] rules exact and roof) are left alone. h_src "<source>~low" and
    "<source>~gen"."""
    if not RECHECK:
        return b
    src = RECHECK["source"]
    col = f"h_{src}"
    if col not in b:
        print(f"recheck: no {col} in the table")
        return b
    exact = b["h_exact"].fillna(False).astype(bool) if "h_exact" in b else pd.Series(False, index=b.index)
    mine = b["h_src"].eq(RECHECK.get("of", "")) & ~exact
    v = pd.to_numeric(b[col], errors="coerce")
    h = b["h"].astype(float)
    low = mine & (h <= RECHECK.get("low", 5.0)) & (v > RECHECK.get("ratio", 2.0) * h)
    gen = pd.Series(False, index=b.index)
    field = RECHECK.get("field")
    if field and field in b and RECHECK.get("diff", 0) > 0:
        f = b[field].astype(str).isin([str(x) for x in RECHECK.get("values", [])])
        gen = mine & ~low & f & v.notna() & ((v - h).abs() > RECHECK["diff"])
        st = RECHECK.get("storeys")
        if st and st in b:
            ref = pd.to_numeric(b[st], errors="coerce").where(lambda x: x > 0) * RECHECK.get("storey_h", LEVEL_H)
            gen &= (v > h) | ref.isna() | ((v - ref).abs() < (h - ref).abs())
    a = b.area
    for m, tag in ((low, "low"), (gen, "gen")):
        b.loc[m, "h"] = v[m]
        b.loc[m, "h_src"] = f"{src}~{tag}"
    print(f"recheck: {int(low.sum()):,} placeholder heights ({a[low].sum():,.0f} m²) and {int(gen.sum()):,} generalised "
          f"solids ({a[gen].sum():,.0f} m², {int((gen & (v > h)).sum()):,} up) take {src}'s")
    return b


GEN_SPLIT = B.get("gen_split", {})


def gen_split(b: gpd.GeoDataFrame, second: gpd.GeoDataFrame | None) -> gpd.GeoDataFrame:
    """[buildings] gen_split ({}: off): a generalised solid of `of` (its `field` one of `values`: the LoD2's roofType
    9999, one flat top for a whole complex) of `min_area` m² or more is split by the second source's footprints
    (`source`: the Umweltatlas, its own heights) clipped to it, each piece at that footprint's height, where those
    heights span `min_range` m or more (the BND's 41,800 m² at 33.3 m over wings from 5.4 m; the Park Center's mall);
    what no footprint covers keeps the solid's height. Pieces with their own exact height are left alone. h_src
    "<source>~split"."""
    if not GEN_SPLIT or second is None or "h" not in second:
        return b
    import shapely
    of, src = GEN_SPLIT.get("of", "lod2"), GEN_SPLIT["source"]
    field, vals = GEN_SPLIT.get("field"), [str(x) for x in GEN_SPLIT.get("values", [])]
    exact = b["h_exact"].fillna(False).astype(bool) if "h_exact" in b else pd.Series(False, index=b.index)
    sel = (b["source"] == of) & ~exact & (b.area >= GEN_SPLIT.get("min_area", 2000.0))
    if "skip" in GEN_SPLIT and "gml_id" in b:            # solids a landmark row reshapes on its own
        sel &= ~b["gml_id"].isin(GEN_SPLIT["skip"])
    if field and field in b:
        sel &= b[field].astype(str).isin(vals)
    sec = second.to_crs(b.crs) if second.crs is not None and second.crs != b.crs else second
    sec = sec[sec.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    sec["geometry"] = sec.geometry.make_valid()
    sec = sec[pd.to_numeric(sec["h"], errors="coerce") > 0]
    tree = shapely.STRtree(sec.geometry.values)
    hs = pd.to_numeric(sec["h"], errors="coerce").values
    min_piece, rng = GEN_SPLIT.get("min_piece", 20.0), GEN_SPLIT.get("min_range", 6.0)
    new, gone, n_split, report = [], [], 0, []
    for i in b.index[sel]:
        g = shapely.make_valid(b.geometry[i])
        cand = tree.query(g, predicate="intersects")
        if len(cand) < 2:
            continue
        pieces, left = [], g
        for j in cand[np.argsort(-hs[cand])]:          # the taller first: a tower over its podium's footprint
            c = shapely.make_valid(left.intersection(sec.geometry.values[j]))
            polys = [p for p in getattr(c, "geoms", [c]) if p.geom_type == "Polygon" and p.area >= 1.0]
            # (a union, not MultiPolygon(polys): pieces sharing an edge make an invalid multipolygon)
            c = shapely.make_valid(shapely.union_all(polys)) if len(polys) > 1 else (polys[0] if polys else None)
            if c is None or c.area < min_piece:
                continue
            pieces.append((c, float(hs[j])))
            left = shapely.make_valid(left.difference(c))
        if len(pieces) < 2 or max(h for _, h in pieces) - min(h for _, h in pieces) < rng:
            continue
        n_split += 1
        report.append((b.at[i, "gml_id"] if "gml_id" in b else i, g.area, float(b.at[i, "h"]),
                       min(h for _, h in pieces), max(h for _, h in pieces), len(pieces)))
        for c, h in pieces:
            r = b.loc[i].copy()
            r["geometry"], r["h"], r["h_src"] = c, h, f"{src}~split"
            new.append(r)
        if left.area >= min_piece:
            b.at[i, "geometry"] = left
        else:
            gone.append(i)
    if not n_split:
        print("gen_split: nothing split")
        return b
    out = pd.concat([b.drop(index=gone), gpd.GeoDataFrame(new, crs=b.crs)], ignore_index=True)
    out = gpd.GeoDataFrame(out, geometry="geometry", crs=b.crs)
    print(f"gen_split: {n_split} generalised solids split into {len(new)} pieces by {src}'s footprints "
          f"({len(gone)} wholly covered)")
    for gid, a, h0, lo, hi, n in sorted(report, key=lambda t: -t[1])[:8]:
        print(f"  {gid}: {a:,.0f} m² at {h0:.1f} m -> {n} pieces {lo:.1f}-{hi:.1f} m")
    return out


CANOPY_FIT = B.get("canopy_fit", {})


def canopy_fit(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """[buildings] canopy_fit ({}: off): the [buildings] rules "roof" pieces (canopies, hall roofs: raised from just
    under their eave) fitted to what they cover. One lying over bodies (other pieces lower than its top, together
    covering `cover` of it) with air between (more than `gap` m, at most `max_down` m: not the roof between twin
    towers over their podium) reaches down to the highest of them (a station's hall roof over its low concourse);
    one over open ground that the eave makes thicker than `thick_max` m (a sloped tent or shell extruded over its whole slope: the Sony
    Center's roof as boxes 8-24 m thick over the forum) becomes a slab `thick` m thick at its top, unless it is
    `slab_max_area` m² or more (a station's hall vault spanning its platforms, for a landmark row to shape) or under
    `slab_min_area` (a gate's roof on posts too thin to cover it). One whose
    body's top lies inside its own span starts there (the Hauptbahnhof's Bügel: the tilted roof planes over their
    office bars, which volume_dedupe otherwise cut out from under them)."""
    if not CANOPY_FIT:
        return b
    import shapely
    labels = [r.get("label", "roof") for r in RULES if r.get("action") == "roof"]
    roof = b["rule"].isin(labels).values if "rule" in b else np.zeros(len(b), bool)
    mh = b["min_h"].astype(float).fillna(0.0).to_numpy(copy=True)
    h = b["h"].astype(float).to_numpy(copy=True)
    geo = shapely.make_valid(b.geometry.values)
    # what a roof covers: any other piece lower than it (a building, or another roof: the Hauptbahnhof's Bügel over
    # the hall's vault)
    tree = shapely.STRtree(geo)
    bidx = np.arange(len(b))
    t_max, thick = CANOPY_FIT.get("thick_max", 3.0), CANOPY_FIT.get("thick", 0.6)
    cover, gap = CANOPY_FIT.get("cover", 0.3), CANOPY_FIT.get("gap", 1.0)
    hall = CANOPY_FIT.get("slab_max_area", float("inf"))
    max_down = CANOPY_FIT.get("max_down", float("inf"))
    small = CANOPY_FIT.get("slab_min_area", 0.0)        # (a gate's roof on its posts: the Zoo's Elefantentor)
    down = slab = onto = 0
    for i in np.flatnonzero(roof & (mh > 0)):
        a = max(geo[i].area, 1e-6)
        js = bidx[tree.query(geo[i], predicate="intersects")]
        js = js[(h[js] < h[i] - thick) & (js != i)]
        top = None
        if len(js):
            ov = shapely.area(shapely.intersection(geo[i], geo[js]))
            if ov.sum() >= cover * a:
                big = ov >= 0.05 * a
                top = float(h[js[big]].max()) if big.any() else float(h[js].max())
        if top is not None:
            if mh[i] > top + gap:
                if mh[i] - top <= max_down:      # (not a roof between twin towers 40 m over their podium)
                    mh[i] = top
                    down += 1
            elif top > mh[i] + 0.05:
                # a roof over its own body's top (the Bügel's tilted roof planes over their office bars): on it, so
                # volume_dedupe doesn't cut the body out from under it (which left the roof as a plank in the air)
                mh[i] = top
                onto += 1
        elif h[i] - mh[i] > t_max and small <= geo[i].area < hall:
            mh[i] = h[i] - thick
            slab += 1
    b["min_h"] = mh.round(2)
    print(f"canopy_fit: {down} roofs down to the bodies they cover, {onto} onto the top of the body under them, {slab} "
          f"thick roofs over open ground now {thick} m slabs at their top")
    return b


FIX_H = B["fix_h"]


def fix_heights(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """[buildings] fix_h ({field = {value = m}}; {}: off): the final height of the pieces whose field has that value
    (a solid the laser or a source got wrong: the Rotes Rathaus tower's 83.7 m to its 74 m parapet), h_src fix_h."""
    n = 0
    for field, vals in FIX_H.items():
        if field not in b:
            print(f"fix_h: no field {field}")
            continue
        for v, h in vals.items():
            rows = b[field].astype(str).eq(str(v))
            if not rows.any():
                print(f"fix_h: no piece with {field} {v}")
            b.loc[rows, "h"] = float(h)
            b.loc[rows, "h_src"] = "fix_h"
            n += int(rows.sum())
    if FIX_H:
        print(f"fix_h: {n} pieces set")
    return b


AFLOAT = B["afloat"]


def afloat(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """[buildings] afloat ({}: off): OSM's fill pieces lying `share` or more in the OSM areas `areas` (natural=water):
    boats, pontoons and floating bars the official layer lacks, drawn at `h` m (not the 10.5 m default) and tagged
    `tag` (osm_building); outlines kept by id ([buildings] keep) and buildings of parts are left alone."""
    if not AFLOAT or "osm_id" not in b:
        return b
    u = osm_areas(AFLOAT.get("areas", ["natural=water"]))
    if u is None:
        return b
    part_of = b["part_of"] if "part_of" in b else pd.Series(np.nan, index=b.index)
    cand = b.index[(b["source"] == "osm") & ~b["osm_id"].isin(KEEP_OSM) & part_of.isna() & b.intersects(u)]
    import shapely
    wet = shapely.area(shapely.intersection(shapely.make_valid(b.geometry[cand].values), u))
    sel = cand[wet >= AFLOAT.get("share", 0.5) * b.area[cand].values]
    b.loc[sel, "h"] = float(AFLOAT.get("h", MIN_H))
    b.loc[sel, "min_h"] = 0.0
    b.loc[sel, "h_src"] = "afloat"
    b.loc[sel, "osm_building"] = AFLOAT.get("tag", "ship")
    print(f"afloat: {len(sel)} OSM pieces on the water at {AFLOAT.get('h', MIN_H)} m: "
          + ", ".join(str(n) for n in b.loc[sel, "name"].dropna().head(8)))
    return b


def dem_low(geoms, points: bool = False) -> np.ndarray:
    """The lowest cell of the [sources] dem under each geometry (UTM; all cells touched), or with points=True the
    value at each point; NaN off the DEM."""
    import rasterio
    import rasterio.mask
    out = np.full(len(geoms), np.nan)
    for f in sources.module(CFG["sources"]["dem"]).tiles():
        with rasterio.open(f) as r:
            gs = gpd.GeoSeries(list(geoms), crs=UTM).to_crs(r.crs).values
            vals = []
            if points:
                vals = [x[0] for x in r.sample([(g.x, g.y) for g in gs])]
            else:
                for g in gs:
                    try:
                        a, _ = rasterio.mask.mask(r, [g], crop=True, all_touched=True, filled=False)
                        a = a[0].astype(float)
                        vals.append(float(a.min()) if a.count() else np.nan)
                    except ValueError:                   # (outside this tile)
                        vals.append(np.nan)
            v = np.asarray(vals, dtype=float)
            if r.nodata is not None:
                v[v == r.nodata] = np.nan
            v[~np.isfinite(v) | (v <= -100)] = np.nan
        out = np.where(np.isnan(out), v, out)
    return out


def split_ground(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """[buildings] split_ground (off by default): a source building cut by roof level (the citygml adapter's
    roof_split: roof_level set, parent_id the building) has one ground, its lowest (ground_z), and each level's
    height counts from it; 06_tiles stands each level on the lowest ground under its own outline. On a slope a
    level stands that much too tall (Roppongi Hills' tower ~10 m up from its lowest corner), so each level loses
    the DEM's rise from the building's lowest cell to the lowest cell under its own outline (up to 40 m; never
    below min_h). Column split_rise (m)."""
    if not B.get("split_ground") or "roof_level" not in b or "parent_id" not in b:
        return b
    sel = b.index[pd.to_numeric(b["roof_level"], errors="coerce").notna().values]
    if not len(sel):
        return b
    low = pd.Series(dem_low(b.loc[sel].geometry.values), index=sel)
    base = low.groupby(b.loc[sel, "parent_id"]).transform("min")
    rise = (low - base).clip(lower=0, upper=40).fillna(0)
    rise = rise.where(b.loc[sel, "h"] - rise >= MIN_H, 0)
    b.loc[sel, "h"] = b.loc[sel, "h"] - rise
    b["split_rise"] = rise.reindex(b.index).round(1)
    moved = rise[rise > 0.5]
    print(f"split_ground: {len(sel):,} roof levels of {b.loc[sel, 'parent_id'].nunique():,} buildings; {len(moved):,} "
          f"lowered by their ground's rise (median {moved.median() if len(moved) else 0:.1f} m, "
          f"max {moved.max() if len(moved) else 0:.1f} m)")
    return b


SLAB = B["slab_drop"]


def slab_base(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Buildings rooted below an artificial ground ([buildings] slab_drop m; 0: off). An official layer's height
    counts from the building's own ground (its ground_elevation: BD TOPO's altitude_minimale_sol, APUR's
    al_med_mnt), but the terrain carries a slab over it where one was built (La Défense's dalle, up to 22 m over
    the old ground under The Link; the Front de Seine's and the Olympiades' slabs): extruded from the terrain,
    such a building would stand that much too tall. Where the DEM at a footprint lies more than slab_drop m (up
    to 40) over its ground_elevation, the height is lowered by the difference (h_src gets "@slab"); a building
    whose top stays under the slab (a car park under the dalle) is dropped. The landmark list's heights count
    from the same ground (The Link: 242 listed, BD TOPO 245 from 22 m under the dalle), so they are lowered too."""
    if not SLAB or "ground_elevation" not in b:
        return b
    import rasterio
    g0 = pd.to_numeric(b["ground_elevation"], errors="coerce")
    scale = b["source"].map(lambda s: CFG["sources"].get(s, {}).get("height_scale", 1.0)
                            if isinstance(CFG["sources"].get(s), dict) else 1.0)
    g0 = g0 * scale
    pts = b.geometry.representative_point()
    dem = pd.Series(np.nan, index=b.index)
    for f in sources.module(CFG["sources"]["dem"]).tiles():
        with rasterio.open(f) as r:
            v = np.array([x[0] for x in r.sample(zip(pts.x.values, pts.y.values))], dtype=float)
            nod = r.nodata
        if nod is not None:
            v[v == nod] = np.nan
        dem = dem.fillna(pd.Series(v, index=b.index).where(v > -100))
    off = dem - g0
    if "part_of" in b:                  # a building made of parts: one offset, its parts' median
        grp = b["part_of"]
        med = off.groupby(grp).median()
        off = off.where(grp.isna(), grp.map(med))
    lift = (off > SLAB) & (off <= 40) & (g0 > 0)
    if B["slab_sources"]:              # only these sources' ground elevations (and their footprints' parts)
        lift &= b["source"].isin(B["slab_sources"])
    buried = lift & (b.h - off < 1.0)
    b.loc[lift, "h"] = b.loc[lift, "h"] - off[lift]
    if "min_h" in b:                   # a lifted part's underside comes down with it
        up = lift & (b["min_h"].fillna(0) > 0)
        b.loc[up, "min_h"] = (b.loc[up, "min_h"] - off[up]).clip(lower=0)
    b.loc[lift, "h_src"] = b.loc[lift, "h_src"].astype(str) + "@slab"
    b["slab"] = off.where(lift).round(1)
    print(f"slab: {int(lift.sum()):,} buildings rooted {SLAB:.0f}+ m under the terrain (median "
          f"{off[lift].median() if lift.any() else 0:.1f} m, max {off[lift].max() if lift.any() else 0:.1f} m) lowered; "
          f"{int(buried.sum()):,} wholly under it dropped")
    if buried.any():
        z = b[buried]
        ll = z.geometry.representative_point().to_crs(4326)
        print("slab: dropped (under the slab): " + "; ".join(
            f"{r.h_src} {r.h + o:.0f} m, {g.area:.0f} m² at {p.y:.5f},{p.x:.5f} (slab {o:.0f} m)"
            for r, g, p, o in zip(z.itertuples(), z.geometry, ll, off[buried])))
    return b[~buried]


def dedupe(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Of two footprints overlapping by 90 % of the smaller (the same building from two sources, or drawn twice),
    the smaller goes; parts of a part-built building are left alone (a spire stands inside its tower's crown)."""
    solid = b["part_of"].isna() if "part_of" in b else pd.Series(True, index=b.index)
    if "osm_deck" in b:                 # [osm] min_height: a deck over its towers is no duplicate of them
        solid &= ~b["osm_deck"].fillna(False).astype(bool)
    s = b[solid]
    j = gpd.sjoin(s[["geometry"]], s[["geometry"]], predicate="intersects")
    j = j[j.index < j.index_right]
    if not len(j):
        return b
    import shapely
    ga, gb = s.geometry.loc[j.index].values, s.geometry.loc[j.index_right].values
    inter = shapely.area(shapely.intersection(ga, gb))
    aa, ab = shapely.area(ga), shapely.area(gb)
    dup = inter >= 0.9 * np.minimum(aa, ab)
    kept = 0
    if B["dedupe_keep_taller"]:
        # a smaller footprint over 1 m taller than the one it lies in is a tower drawn inside its building's
        # outline (a cadastre's solids overlapping): it stays, and volume_dedupe cuts it out of the lower one
        h = b["h"].astype(float)
        ha, hb = h.loc[j.index].values, h.loc[j.index_right].values
        taller = np.where(aa < ab, ha > hb + 1.0, hb > ha + 1.0)
        kept = int((dup & taller).sum())
        dup &= ~taller
    drop = set(np.where(aa[dup] < ab[dup], j.index[dup], j.index_right[dup]))
    print(f"dedupe: {len(drop):,} footprints lying 90 %+ inside another dropped"
          + (f", {kept:,} taller than it kept" if B["dedupe_keep_taller"] else ""))
    return b.drop(index=list(drop))


def over_water(b: gpd.GeoDataFrame, osm: gpd.GeoDataFrame | None) -> gpd.GeoDataFrame:
    """[buildings] water = {path, deck} ({}: off): footprints over water (path: polygons in raw/, London's OS
    OpenMap Local tidal water) that are a fill source's or an OSM building with a layer of 1 or more (a station on a
    bridge: Blackfriars, and its parts) stand on a deck: what lies over the water starts at `deck` m (min_h) where
    the building rises 2 m or more over it, else it goes; the rest stays on the ground. OSM buildings on the ground
    (a bridge's towers on their piers) are left alone."""
    W = B["water"]
    if not W:
        return b
    from shapely.geometry import box
    import shapely
    w = gpd.read_file(RAW / W["path"], bbox=tuple(gpd.GeoSeries([box(*b.total_bounds)], crs=UTM)
                                                    .to_crs(gpd.read_file(RAW / W["path"], rows=1).crs).total_bounds))
    # (OS OpenMap Local's polygons carry Z: flat, or the wet pieces cut from them are 3D and break 06_tiles' earcut)
    w = shapely.force_2d(w.to_crs(UTM).geometry.make_valid().union_all())
    deck = float(W["deck"])
    part_of = b["part_of"] if "part_of" in b else pd.Series(np.nan, index=b.index)
    layer = pd.Series(0.0, index=b.index)
    if osm is not None and "osm_id" in b:
        lay = pd.to_numeric(osm.drop_duplicates("osm_id").set_index("osm_id")["layer"], errors="coerce")
        layer = b["osm_id"].map(lay).fillna(0)
    # (an OSM building's parts carry its osm_id and so its layer: Blackfriars' station is mapped in parts)
    cand = b.index[((b["source"] != "osm") | (layer >= 1)) & b.intersects(w)]
    rows, drop, lifted, gone = [], [], 0, 0
    for i in cand:
        r = b.loc[i]
        wet = r.geometry.intersection(w)
        if wet.area < 20:
            continue
        dry = r.geometry.difference(w)
        drop.append(i)
        if r["h"] >= deck + 2:
            rows.append({**r.drop("geometry").to_dict(), "min_h": max(deck, float(r.get("min_h", 0) or 0)),
                         "geometry": wet})
            lifted += 1
        else:
            gone += 1
        if not dry.is_empty and dry.area >= MIN_PIECE:
            rows.append({**r.drop("geometry").to_dict(), "geometry": dry})
    print(f"water: {lifted} footprints over water stand on a {deck:g} m deck there, {gone} lower ones lose what lies "
          "over it")
    if not rows:
        return b
    out = gpd.GeoDataFrame(rows, crs=UTM)
    out = out[out.geom_type.isin(["Polygon", "MultiPolygon"]) | out.geometry.apply(lambda g: g.geom_type == "GeometryCollection")]
    out["geometry"] = [shapely.union_all([p for p in getattr(g, "geoms", [g]) if p.geom_type in ("Polygon", "MultiPolygon")])
                       for g in out.geometry]
    out = out[~out.geometry.is_empty & (out.area >= MIN_PIECE)]
    return gpd.GeoDataFrame(pd.concat([b.drop(index=drop), out], ignore_index=True), crs=UTM)


def volume_dedupe(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """[buildings] volume_dedupe: two pieces overlapping on the map (by 10 % of the smaller, 5 m² or more) and in
    height (by more than a metre: neither stands on the other) are one volume drawn twice; the lesser is clipped by
    the better (OSM's over a fill source's, then the taller), and goes when less than min_piece m² is left."""
    if not B["volume_dedupe"]:
        return b
    import shapely
    geo = shapely.make_valid(b.geometry.values)
    j = gpd.sjoin(b[["geometry"]].reset_index(names="i"), b[["geometry"]].reset_index(names="k"), predicate="intersects")
    j = j[j.i < j.k]
    ii, kk = j.i.values, j.k.values
    pos = pd.Series(np.arange(len(b)), index=b.index)
    gi, gk = geo[pos[ii].values], geo[pos[kk].values]
    inter = shapely.area(shapely.intersection(gi, gk))
    small = np.minimum(shapely.area(gi), shapely.area(gk))
    h, m = b["h"].astype(float), b["min_h"].fillna(0).astype(float)
    vert = np.minimum(h[ii].values, h[kk].values) - np.maximum(m[ii].values, m[kk].values)
    dup = (inter >= np.maximum(5.0, 0.1 * small)) & (vert > 1.0)
    if "osm_deck" in b:            # [osm] min_height: a deck over its towers shares their height range, not their volume
        deck = b["osm_deck"].fillna(False).astype(bool)
        dup &= ~(deck[ii].values | deck[kk].values)
    if "part_of" in b:             # a building's own parts are layered by use_parts (a slab over the parts under it)
        po = b["part_of"]
        dup &= ~(po[ii].notna().values & (po[ii].values == po[kk].values))
    ii, kk = ii[dup], kk[dup]
    rank = (b["source"] == "osm").astype(int) * 1e6 + b["h"].astype(float)
    lose = np.where(rank[ii].values < rank[kk].values, ii, kk)
    win = np.where(rank[ii].values < rank[kk].values, kk, ii)
    drop, clipped = [], 0
    for i, ws in pd.Series(win).groupby(lose):
        g = shapely.difference(geo[pos[i]], shapely.union_all(geo[pos[ws.values].values]))
        g = shapely.make_valid(g)
        polys = [p for p in getattr(g, "geoms", [g]) if p.geom_type in ("Polygon", "MultiPolygon")]
        g = shapely.union_all(polys) if polys else None
        if g is None or g.is_empty or g.area < MIN_PIECE:
            drop.append(i)
        else:
            b.at[i, "geometry"] = g
            clipped += 1
    print(f"volume dedupe: {len(ii):,} pairs drawn twice: {clipped:,} pieces clipped, {len(drop):,} dropped")
    return b.drop(index=drop)


def assign_heights(b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """h and h_src from the height sources, in the order of priority HEIGHTS (landmarks apart: main()).
    Applied from the lowest priority up, each where it has a value: default and cnbh fill what nothing else
    gives, the others override."""
    b["h"], b["h_src"] = np.nan, None
    bl = B["blend"]
    for src in reversed([h for h in HEIGHTS if h != "landmark"]):
        if src == "default":
            v, ok = pd.Series(B["default_floors"] * LEVEL_H, index=b.index), b["h"].isna()
        elif src == "blend":
            a, c = (b[f"h_{k}"] for k in bl["sources"])
            mean_est = b[[f"h_{k}" for k in bl["sources"]]].mean(axis=1)
            v = bl["weights"][0] * a + bl["weights"][1] * c
            ok = mean_est.between(*bl["band"]) & a.notna() & c.notna()
        elif src in ("osm_height", "osm_levels"):
            col = "h_osm_tag" if src == "osm_height" else "h_osm_levels"
            v, ok = b[col], b[col].notna() & (b[col] > 0)
            # a tall OSM building's height only on a footprint that is a good share of it (NEEDLE share): an
            # official layer's heightless wing inside a tower's OSM outline is not the tower (Tour First's 666 m²
            # north wing, 18 % of its outline, took its 225 m)
            if "osm_share" in b:
                ok &= (v < NEEDLE["height"]) | (b["osm_share"] >= NEEDLE["share"])
        else:
            v, ok = b[f"h_{src}"], b[f"h_{src}"].notna()
        b.loc[ok, "h"] = v[ok]
        b.loc[ok, "h_src"] = src
    return b


def landmark_report(b: gpd.GeoDataFrame) -> list:
    """Every must-have row (notes say MUST-HAVE) and every row of 150 m or more: listed against built; the
    structures' surroundings (nothing tall where a figure will stand); rows outside every district; rows whose
    point is not on the building they set."""
    if not LANDMARKS:
        return []
    lm = pd.concat([pd.read_csv(f) for f in LANDMARKS], ignore_index=True).dropna(subset=["lat", "lon"])
    pts = gpd.GeoDataFrame(lm, geometry=[Point(xy) for xy in zip(lm.lon, lm.lat)], crs="EPSG:4326").to_crs(UTM)
    must = lm.get("notes", pd.Series("", index=lm.index)).fillna("").str.contains("MUST")
    feature = lm["feature"].fillna("building") if "feature" in lm else pd.Series("building", index=lm.index)
    lc = pd.DataFrame(LANDMARK_CHECK, columns=["name", "listed", "data", "src", "d"]).drop_duplicates("name")
    lc = lc.set_index("name")
    has = b["landmark"] if "landmark" in b else pd.Series(None, index=b.index)
    top = b.groupby(has).h.max()
    roof = {}
    if "part_of" in b:
        for n, g in b[has.notna() & b.part_of.notna()].groupby(has):
            roof[n] = main_roof(g)
    srcs = b.groupby(has).h_src.agg(lambda v: ", ".join(sorted(set(map(str, v)))[:3]))
    slab = b.groupby(has).slab.max() if "slab" in b else pd.Series(dtype=float)
    poly = boundary().geometry.iloc[0]
    L = ["", "## Must-have landmarks and every listed building of 150 m or more", "",
         "Listed: the landmark list's height (its type); built: the building's top in the table, above the terrain "
         "(made of OSM parts: its main roof / its top); d: metres from the list's point to the building it set (0: "
         "on it). A building rooted under a slab (slab_base) stands lower above the terrain by the slab's height.", "",
         "| Landmark | listed (m) | type | use | built (m) | h from | d (m) | note |", "|---|---|---|---|---|---|---|---|"]
    sel = lm[must | (lm.height_m >= 150)].sort_values("height_m", ascending=False)
    for i, r in sel.iterrows():
        n = r["name_zh"]
        inside = pts.geometry[i].within(poly)
        if feature[i] == "structure":
            built, note = "—", "structure: not a building (a [[structures]] figure)"
        elif n in top.index:
            built = f"{roof[n]:.0f} / {top[n]:.0f}" if n in roof else f"{top[n]:.0f}"
            note = "" if inside else "outside the districts"
            if pd.notna(slab.get(n)):
                note = (f"stands {slab[n]:.0f} m under the terrain (a slab): {top[n] + slab[n]:.0f} m from its own "
                        "ground " + note).strip()
        else:
            built, note = "—", "not matched" + ("" if inside else " (outside the districts)")
        d = f"{lc.d[n]:.0f}" if n in lc.index else ""
        L.append(f"| {n} | {r.height_m:.0f} | {r.get('height_type', '')} | {r.use_height} | {built} | "
                 f"{srcs.get(n, '')} | {d} | {note} |")
    far = lc[lc.d > 0]
    L += ["", f"Rows whose point is not on the building they set: {len(far)}"
          + (" (" + ", ".join(f"{n} {r.d:.0f} m" for n, r in far.sort_values("d", ascending=False).iterrows()) + ")"
             if len(far) else "") + ". One building per row, one row per building (match: "
          f"{LM['match']}).",
          "", "Rows outside every district: " + (", ".join(lm.name_zh[~pts.within(poly)]) or "none") + ".", ""]
    st = pts[feature.eq("structure")]
    if len(st):
        L += ["Structures (drawn as figures, not buildings): the tallest building within 150 m of each.", "",
              "| Structure | listed (m) | tallest building within 150 m (m) |", "|---|---|---|"]
        for i, r in st.iterrows():
            near = b[b.intersects(r.geometry.buffer(150))]
            L.append(f"| {r['name_zh']} | {r.height_m:.0f} | {near.h.max() if len(near) else 0:.0f} |")
        L.append("")
    return L


def remap_kinds(kind: pd.Series) -> pd.Series:
    """[buildings] kind_map ({kind = other}; {}: off): kinds the preset's shape rules give that a city has none of,
    as another of the preset's kinds (Hong Kong: china-south's urban "village", 12-40 m on a small plot, is tong lau
    and pencil towers there: "midrise"); after every other kind rule."""
    if not KIND_MAP:
        return kind
    out = kind.replace(KIND_MAP)
    print("kind_map: " + ", ".join(f"{k} -> {v}: {int((kind == k).sum()):,}" for k, v in KIND_MAP.items()))
    return out


def valid_out(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """[buildings] valid_out (false: off): the table's geometries repaired as written (after the reprojection to
    WGS84, which can fold a clipped piece's slivers): make_valid, polygons only, empty pieces dropped."""
    if not B["valid_out"]:
        return g
    import shapely
    bad = ~g.geometry.is_valid
    if bad.any():
        fixed = shapely.make_valid(g.geometry[bad].values)
        fixed = [shapely.union_all([p for p in getattr(x, "geoms", [x]) if p.geom_type in ("Polygon", "MultiPolygon")])
                 if x.geom_type not in ("Polygon", "MultiPolygon") else x for x in fixed]
        g = g.copy()
        g.loc[bad, "geometry"] = fixed
        g = g[~g.geometry.is_empty & g.geometry.notna()]
    print(f"valid_out: {int(bad.sum()):,} invalid geometries repaired; invalid left {int((~g.geometry.is_valid).sum())}")
    return g


KIND_MAP = B["kind_map"]


def main():
    poly = boundary().geometry.iloc[0]
    osm = deck_rule(osm_overrides(load_osm(underground=B["surface_layers"]), "OSM buildings"))
    osm_low = None
    if B["surface_layers"]:             # those under ground are sorted once the fill sources are loaded
        layer = pd.to_numeric(osm["layer"], errors="coerce").fillna(0)
        low = (osm["location"] == "underground") | (layer < 0)
        osm_low, osm = osm[low & (osm["location"] != "underground")], osm[~low]
    # inside by their representative point: a building mostly beyond the edge (a market across the city limit)
    # is not the scene's
    skip = osm["building"].isin(B["osm_skip"]) & ~osm["osm_id"].isin(KEEP_OSM)
    if STATION_DROP or STATION_H is not None:
        st = untagged_stations(osm)
        if STATION_DROP:                # left out like osm_skip's (no fill source builds there either)
            skip |= st
            print(f"station_untagged: {int(st.sum())} untagged station outlines dropped")
        else:
            _STATION_IDS.update(osm["osm_id"][st])
    _SKIPPED.extend(osm.geometry[skip])
    osm = osm[osm.geometry.representative_point().within(poly) & ~skip].copy()
    blocks, pieces, with_h, primaries = [], [], [], []
    for name in FOOTPRINTS:
        if name == "osm":
            continue
        src = sources.module(name)
        g = src.load()
        if src.ROLE == "primary":
            g = g[g.intersects(poly) & g.geom_type.isin(["Polygon", "MultiPolygon"])]
            for col, vals in B["exclude"].items():            # demolished since the layer's snapshot
                if col != "osm" and col in g:
                    g = g[~g[col].isin(vals)]
            if RULES:
                g = primary_rules(g, name)
            g = g.reset_index(drop=True)
            g = split_merged(g, osm if "osm" in FOOTPRINTS else None)
            primaries.append((name, g))
        elif src.ROLE == "pieces":
            g["geometry"] = g.geometry.make_valid()
            g = g[g.area >= MIN_PIECE].reset_index(drop=True)
            pieces.append((name, align_pieces(g, osm) if getattr(src, "ALIGN", True) else g))
        else:
            g = g[g.intersects(poly)].copy()
            if RULES and any(r.get("source") == name for r in RULES):     # a fill source's own rules (by name)
                g = primary_rules(g, name, named_only=True).drop(columns=["keep_small", "h_exact"])
            blocks.append((name, g))
            if src.ROLE == "fill":
                _FILLS.add(name)
        if src.HEIGHTS:
            with_h.append((name, g))

    if osm_low is not None and len(osm_low):
        up = surface_layers(osm_low[osm_low.geometry.representative_point().within(poly)
                                    & ~osm_low["building"].isin(B["osm_skip"])],
                            [g for n, g in blocks if n in _FILLS and "h" in g])
        osm = pd.concat([osm, up]).copy()
    _PART_OUTLINES.update(part_outlines(osm))
    primary = primaries[0] if len(primaries) == 1 else (primaries or None)
    b = choose_footprints(osm if "osm" in FOOTPRINTS else None, blocks, pieces, primary)
    for name, g in with_h:
        if name in dict(primaries):
            # its own footprints: their own heights and fields; any other footprint it covers (OSM's fill,
            # another primary's), the height of its polygon there
            own = b["source"] == name
            h = source_height(b[~own], g)["h"] if (~own).any() else pd.Series(dtype=float)
            b[f"h_{name}"] = h.reindex(b.index)
            b.loc[own, f"h_{name}"] = b.loc[own, "pid"].map(g["h"])
            for col in g.columns.difference(["geometry", "h", "source", "h_split", "split_of"]):
                v = b.loc[own, "pid"].map(g[col])
                b[col] = v.reindex(b.index) if col not in b else b[col].where(~own, v.reindex(b.index))
        else:
            sh = source_height(b, g)
            b[f"h_{name}"] = sh["h"]
            b[f"join_{name}"] = sh["join"]
            if "h_mean" in sh:
                b[f"hmean_{name}"] = sh["h_mean"]
    for name, g in with_h + [(n, g) for n, g in primaries if n not in dict(with_h)]:
        lend_fields(b, name, g)

    attach_osm(b, osm)
    if "h_split" in b:                                   # split footprints: their OSM building's height
        b["h_osm_tag"] = b["h_split"].where(b["h_split"].notna(), b["h_osm_tag"])
    for name in HEIGHTS:
        if name in sources.RASTER_HEIGHTS:
            b[f"h_{name}"] = sources.module(name).sample(b)
    print(f"footprints: {b.source.value_counts().to_dict()}")

    b = assign_heights(b)
    b.loc[b["h_src"].isna(), "h_src"] = "default"
    b = split_ground(b)
    b = recheck(b)
    b = gen_split(b, dict(with_h).get(GEN_SPLIT.get("source")) if GEN_SPLIT else None)
    b = despike(b, osm)
    b = reconcile(b)
    b = copied(b)
    if B["parts"]:
        b = use_parts(b, osm)
        b["geometry"] = b.geometry.make_valid()
        b = b[b.geom_type.isin(["Polygon", "MultiPolygon"])]
    b = dedupe(b)
    b = split_podiums(b, dict(with_h))     # (after use_parts: a building made of parts is no podium)
    b = landmark_podiums(b)
    n_lm = apply_landmarks(b) if "landmark" in HEIGHTS else 0
    b = slab_base(b)
    b = fix_heights(b)
    b = station_sheds(b)
    # small things nothing knows the height of (sheds, kiosks OSM adds): one storey, not three
    small = (b.h_src == "default") & (b.area < 50)
    b.loc[small, "h"] = MIN_H
    exact = b["h_exact"].fillna(False).astype(bool) if "h_exact" in b else pd.Series(False, index=b.index)
    b["h"] = b["h"].where(exact, b["h"].clip(lower=MIN_H)).round(1)
    if "min_h" not in b:
        b["min_h"] = 0.0
    b["min_h"] = b["min_h"].fillna(0.0)
    b = cantilevers(b)
    b["min_h"] = np.maximum(b["min_h"].fillna(0.0), nested(b))
    print(f"raised: {(b.min_h > 0).sum():,} buildings start above the ground (on a roof, overhangs)")
    # on a roof: its own height on top of the roof's, where it is lower than the roof
    low = (b.min_h > 0) & (b.h <= b.min_h) & ~own_ground(b)
    b.loc[low, "h"] = b.min_h[low] + np.maximum(b.h[low], MIN_H)
    b = set_heights(b)
    b = over_water(b, osm)
    b = afloat(b)
    b = canopy_fit(b)
    b = volume_dedupe(b)
    b["floors"] = (b["h"] / LEVEL_H).round().clip(lower=1).astype(int)

    st = shape_stats(b)
    b = b.join(st)
    b["kind"] = presets.module().building_kind(b)
    b["h_bldg"] = b["h"]
    if "part_of" in b:
        # a building made of parts is one kind, from the whole of it (its outline and its top)
        parts = b[b.part_of.notna()]
        fields = getattr(presets.module(), "KIND_FIELDS",
                         ("osm_building", "bldgclass", "numfloors", "yearbuilt", "construction_year"))
        agg = {c: "first" for c in fields if c in parts}
        whole = parts.dissolve("part_of", aggfunc={"h": "max", **agg})
        whole["h"] = parts.groupby("part_of").apply(main_roof).reindex(whole.index)
        whole = whole.join(shape_stats(whole))
        b.loc[parts.index, "kind"] = parts.part_of.map(presets.module().building_kind(whole)).values
        roofs = parts.groupby("part_of").apply(main_roof)
        b.loc[parts.index, "h_bldg"] = parts.part_of.map(roofs).values

    b["kind"] = remap_kinds(b["kind"])

    if "eave_z" in b and "ground_elevation" in b:
        # the eave over the piece's ground (a source with eaves: the LoD2's), for walls to the eave and a roof above
        # it; only where the piece keeps its source's own top (not a height another source or rule set)
        eave = pd.to_numeric(b["eave_z"], errors="coerce") - pd.to_numeric(b["ground_elevation"], errors="coerce")
        own_top = pd.to_numeric(b["roof_top_z"], errors="coerce") - pd.to_numeric(b["ground_elevation"], errors="coerce") \
            if "roof_top_z" in b else b["h"]
        b["eave_h"] = eave.clip(lower=0).where((b["h"] - own_top).abs() <= 1.0).clip(upper=b["h"]).round(1)
    out = valid_out(b.drop(columns=["length", "width"]).to_crs("EPSG:4326"))
    out.to_file(DATA / "buildings.gpkg")

    L = [f"# {CFG['title']} building table", "",
         f"{len(b):,} buildings (footprints: {b.source.value_counts().to_dict()}), "
         f"{b.area.sum() / 1e6:.1f} km² footprint, {n_lm} landmark heights applied.", "",
         "| Footprint source | buildings | share | footprint area share |", "|---|---|---|---|"]
    for src, g in b.groupby("source"):
        L.append(f"| {src} | {len(g):,} | {len(g) / len(b):.1%} | {g.area.sum() / b.area.sum():.1%} |")
    if RULE_COUNTS:
        L += ["", "[buildings] rules on the primary footprints (first match wins; counted where the rule matched, "
              "before footprints were chosen):", "", "| Source | rule | action | footprints | area (m²) |",
              "|---|---|---|---|---|"]
        L += [f"| {s} | {lab} | {act} | {n:,} | {a:,.0f} |" for s, lab, act, n, a in RULE_COUNTS]
    L += ["", "| Height source | buildings | share | median h (m) | max h (m) |", "|---|---|---|---|---|"]
    for src, g in b.groupby("h_src"):
        L.append(f"| {src} | {len(g):,} | {len(g) / len(b):.1%} | {g.h.median():.1f} | {g.h.max():.0f} |")
    L += ["", "| Kind | buildings | share | footprint area share | median h (m) | median footprint (m²) |",
          "|---|---|---|---|---|---|"]
    for k, g in b.groupby("kind"):
        L.append(f"| {k} | {len(g):,} | {len(g) / len(b):.1%} | {g.area.sum() / b.area.sum():.1%} | "
                 f"{g.h.median():.1f} | {g.area.median():.0f} |")
    if "slab" in b:
        sl = b[b.slab.notna()]
        L += ["", f"Rooted under a slab (slab_base, [buildings] slab_drop {SLAB:g} m): {len(sl):,} buildings lowered "
              f"by the terrain's height over their own ground (median {sl.slab.median() if len(sl) else 0:.1f} m, "
              f"max {sl.slab.max() if len(sl) else 0:.1f} m)."]
    # count buildings, not pieces: a building made of parts, or the pieces a landmark names, is one
    key = pd.Series([f"i{i}" for i in b.index], index=b.index)
    if "landmark" in b:
        key = key.where(b["landmark"].isna(), "l" + b["landmark"].astype(str))
    if "part_of" in b:
        key = key.where(b["part_of"].isna(), "p" + b["part_of"].astype(str))
    whole = b.assign(key=key).sort_values("h", ascending=False).drop_duplicates("key")
    L += ["", f"Buildings (a building made of parts, or a landmark's pieces, counted once) ≥ 100 m: "
          f"{(whole.h >= 100).sum()}, ≥ 150 m: {(whole.h >= 150).sum()}, ≥ 200 m: {(whole.h >= 200).sum()} "
          f"({(b.h >= 100).sum()}, {(b.h >= 150).sum()}, {(b.h >= 200).sum()} pieces). Tallest: "
          + ", ".join(f"{r['name'] if pd.notna(r['name']) else '(unnamed)'} {r['h']:.0f} m ({r['h_src']})"
                      for _, r in whole.head(8).iterrows()) + "."]
    if LANDMARK_CHECK:
        lc = pd.DataFrame(LANDMARK_CHECK, columns=["name", "listed", "data", "src", "d"])
        lc.to_csv(DATA / "landmark_check.csv", index=False)      # every matched row, for a city's own checks
        lc["d"] = lc.data - lc.listed
        L += ["", f"## Landmarks against the data ({len(lc)} matched)", "",
              "The hand-checked list (data/landmarks*.csv, from CTBUH and Wikipedia: independent of the footprint "
              "sources) against the height the data gave the building before the list overrode it. A building made "
              "of OSM parts keeps its parts (the list only names it); its main roof here is where its parts, "
              "from the top down, add up to 60 m² (main_roof), so spires and masts don't count, while the list gives roof or, where CTBUH "
              "has none, architectural heights (height_type).", "",
              f"Median data − list {lc.d.median():+.1f} m, median abs {lc.d.abs().median():.1f} m; within 10 m: "
              f"{(lc.d.abs() <= 10).mean():.0%}. Largest differences:", "",
              "| Landmark | listed (m) | data (m) | from |", "|---|---|---|---|"]
        for r in lc.reindex(lc.d.abs().sort_values(ascending=False).index).head(15).itertuples():
            L.append(f"| {r.name} | {r.listed:.0f} | {r.data:.0f} | {r.src} |")
    L += landmark_report(b)
    (CHECKS / "buildings.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))

