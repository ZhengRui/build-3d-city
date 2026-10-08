"""M3 checks for Berlin: the water against its banks, roads through buildings, the railways on the Stadtbahn's arches,
and the named spots' heights in the scene. Run from demos/berlin after 06_tiles: `uv run python scripts/m3_checks.py`.
Writes checks/water.md and checks/clearance.md (the 06_tiles counts from checks/road_clearance.md quoted).
"""
import tomllib
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely
from pyproj import Transformer

from city3d.common import DATA, UTM, Terrain, boundary
from city3d.stages.tiles import ROAD_Y

HERE = Path(__file__).resolve().parents[1]
CHECKS = HERE / "checks"
T = Terrain()
rng = np.random.default_rng(3)


def level_of(g):
    """The modal TIN height inside a water body (06_tiles' water_levels: quay walls drop the cells along it)."""
    x0, y0, x1, y1 = g.bounds
    n = int(min(max(g.area / 25, 200), 20000))
    q = np.column_stack([rng.uniform(x0, x1, n * 3), rng.uniform(y0, y1, n * 3)])
    q = q[shapely.contains_xy(g, q[:, 0], q[:, 1])][:n]
    if len(q) < 20:
        return None
    v, c = np.unique(np.round(T.height_utm(q[:, 0], q[:, 1]), 2), return_counts=True)
    return float(v[np.argmax(c)]) if c.max() >= 0.3 * len(q) else None


def water():
    to_ll = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    w = gpd.read_file(DATA / "ground.gpkg", layer="water")
    area = boundary().geometry.iloc[0].buffer(1000)
    w = w[(w.area >= 3000) & w.intersects(area)].reset_index(drop=True)
    allw = w.union_all()
    rows = []
    for i, g in enumerate(w.geometry):
        lv = level_of(g)
        if lv is None:
            continue
        ring = g.buffer(8).exterior if g.geom_type == "Polygon" else g.buffer(8).boundary
        pts = [ring.interpolate(d) for d in np.arange(0, ring.length, 5.0)]
        P = np.array([[p.x, p.y] for p in pts])
        # bank points only: not in another water body, not under a bridge's water joining
        dry = ~shapely.contains_xy(allw, P[:, 0], P[:, 1])
        P = P[dry]
        if len(P) < 10:
            continue
        h = T.height_utm(P[:, 0], P[:, 1]) - lv
        c = g.representative_point()
        lon, lat = to_ll.transform(c.x, c.y)
        rows.append((g.area / 1e4, lat, lon, lv, len(P), float((h < -0.1).mean()), float(np.median(h)),
                     float(np.percentile(h, 10))))
    rows.sort(reverse=True)
    tot = sum(r[4] for r in rows)
    under = sum(r[4] * r[5] for r in rows)
    lines = ["# Water against its banks (M3, scripts/m3_checks.py)", "",
             "Every levelled water body over 0.3 ha within 1 km of the districts: its level (the modal height of the "
             "scene's ground inside it, as 06_tiles draws it), and the ground 8 m outside its outline every 5 m (points "
             "in another water body left out) against that level. A bank point under the water (< -0.1 m) is where "
             "the water would spill or a gap show between it and its wall; the quay walls (05a_terrain "
             "`quay_walls`, 05e_shores' faces) stand on the first land cells.", "",
             f"{len(rows)} bodies, {tot:,} bank points, {under / max(tot, 1) * 100:.1f} % under their water's level.", "",
             "| Body (a point in it) | ha | level, scene y (m; + 30 = m NHN) | bank points | under the level | bank over the level: median, p10 (m) |",
             "|---|---|---|---|---|---|"]
    for a, lat, lon, lv, n, sh, med, p10 in rows[:30]:
        lines.append(f"| {lat:.5f}, {lon:.5f} | {a:.1f} | {lv:.2f} ({lv + 30:.2f}) | {n} | {sh * 100:.1f} % | {med:.1f}, {p10:.1f} |")
    return lines


def clearance():
    b = gpd.read_file(DATA / "buildings.gpkg", engine="pyogrio",
                      columns=["source", "function", "h", "min_h", "osm_id", "gml_id", "name"]).to_crs(UTM)
    r = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    ground = r[~r.elevated.astype(bool)]
    def buffers(kind, less):
        part = ground[ground.kind == kind]
        return shapely.buffer(part.geometry.force_2d().values, (part.width.values * 0.5 - less).clip(0.5), cap_style="flat")

    def share_on(geo, bufs):
        """Each footprint's share on the road buffers (pairs by STRtree; overlapping buffers counted once each)."""
        tree = shapely.STRtree(bufs)
        i, j = tree.query(geo, predicate="intersects")
        a = shapely.area(shapely.intersection(geo[i], bufs[j]))
        out = np.bincount(i, weights=a, minlength=len(geo)) / shapely.area(geo)
        return np.minimum(out, 1.0)

    core, mcore = buffers("major", 1.0), buffers("minor", 0.5)
    lines = ["# Clearance: roads, railways and buildings (M3, scripts/m3_checks.py)", ""]
    rc = CHECKS / "road_clearance.md"
    if rc.exists():
        lines += ["## Fill footprints dropped by 06_tiles (`road_clearance.md`)", "", *rc.read_text().splitlines()[1:], ""]
    lines += ["## Footprints over carriageways", "",
              "Every footprint of the building table against the ground-level carriageways (major roads' core: half "
              "the width less 1 m; minor roads' less 0.5 m). The LoD2's footprints are the cadastre's: a building "
              "over a road is a real one (a bridge building, a passage, a station hall), so they are counted, not "
              "dropped.", "",
              "| Source | footprints | 30 % or more on a major road's core | 60 % or more on a minor road's core |",
              "|---|---|---|---|"]
    examples = []
    for src, part in b.groupby("source"):
        geo = part.geometry.values
        on_major = share_on(geo, core)
        on_minor = share_on(geo, mcore)
        hit = part[(on_major >= 0.3)]
        examples += [(src, row.osm_id or row.gml_id, row.function, row.h, row.min_h, g.representative_point())
                     for row, g in zip(hit.itertuples(), hit.geometry)][:15]
        lines.append(f"| {src} | {len(part):,} | {(on_major >= 0.3).sum():,} | {(on_minor >= 0.6).sum():,} |")
    if examples:
        to_ll = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
        lines += ["", "Examples (30 % or more on a major road):", "", "| source | id | function | h | min_h | lat, lon |",
                  "|---|---|---|---|---|---|"]
        for src, i, f, h, mh, p in examples[:25]:
            lon, lat = to_ll.transform(p.x, p.y)
            lines.append(f"| {src} | {i} | {f} | {h:.1f} | {mh:.1f} | {lat:.5f}, {lon:.5f} |")
    # the Stadtbahn's tracks against the LoD2's viaduct structures (51009_1750 within 2 m of an elevated railway)
    rail = r[r.elevated.astype(bool) & (r.kind == "rail")].reset_index(drop=True)
    via = b[b.function.fillna("").str.startswith("51009_1750")]
    pairs = gpd.sjoin(via[["h", "min_h", "geometry"]], gpd.GeoDataFrame(geometry=rail.geometry.buffer(2.0), crs=UTM),
                      predicate="intersects")
    diffs, over = [], []
    for i in pairs.index.unique():
        g = via.geometry.loc[i]
        p = g.representative_point()
        top = float(T.bases([g])[0]) + float(via.h.loc[i])      # as 06_tiles stands it: on its lowest ground
        near = rail.geometry.iloc[np.unique(pairs.loc[[i], "index_right"].values)]
        zs = []
        for ln in near:
            c = np.asarray(ln.coords)
            k = np.argmin(np.hypot(c[:, 0] - p.x, c[:, 1] - p.y))
            zs.append(c[k, 2])
        diffs.append(top - (max(zs) + ROAD_Y))
    d = np.array(diffs)
    lines += ["", "## The Stadtbahn and the other viaducts on their arches", "",
              "The LoD2 keeps the listed viaducts' arches (the Stadtbahn through Mitte, function 51009_1750) as structures "
              "at their laser height; the tracks (05b_roads: `rail_layer_h` 9.5, the Stadtbahn as a decks span 7.0 m "
              "over the ground, level over the Spree from its banks) should run on top of them. Each such structure "
              "within 2 m of an elevated railway: its top (the lowest ground under its outline + its height, as 06_tiles stands it) against the "
              "nearest track node's drawn deck top (the way's height + 06_tiles' ROAD_Y).", ""]
    if len(d):
        lines += [f"{len(d)} structures: top − deck p10 / median / p90 = {np.percentile(d, 10):+.1f} / "
                  f"{np.median(d):+.1f} / {np.percentile(d, 90):+.1f} m; {(d > 0.5).mean() * 100:.0f} % over the deck "
                  f"by more than 0.5 m, {(d < -3).mean() * 100:.0f} % more than 3 m under it."]
        lines += [f"Within 0.5 m: {(np.abs(d) < 0.5).mean() * 100:.0f} %; within 1 m: {(np.abs(d) < 1).mean() * 100:.0f} %."]
    # buildings in the water: no footprint more than half over the water unless on a bridge deck (an outline)
    wat = gpd.read_file(DATA / "ground.gpkg", layer="water")
    wat = wat[wat.area >= 200].union_all()
    import pyogrio
    decks = gpd.read_file(DATA / "roads.gpkg", layer="outlines").union_all() \
        if "outlines" in {l[0] for l in pyogrio.list_layers(DATA / "roads.gpkg")} else None
    near = b[b.intersects(wat)]
    share = near.geometry.intersection(wat).area / near.area
    on_deck = near.geometry.intersection(decks).area / near.area if decks is not None else share * 0
    bad = near[(share > 0.5) & (on_deck < 0.5)]
    lines += ["", "## Buildings in the water", "",
              "Footprints of the building table more than 50 % over the water layer (bodies of 200 m² or more) and "
              "not on a bridge outline (05b_roads' outlines).", "",
              f"{len(bad)} footprints (of {len(near):,} touching the water)."]
    if len(bad):
        to_ll = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
        lines += ["", "| source | id | name | h | area m² | in water | lat, lon |", "|---|---|---|---|---|---|---|"]
        for i, row in bad.iterrows():
            p = row.geometry.representative_point()
            lon, lat = to_ll.transform(p.x, p.y)
            ident = row.get("osm_id") if isinstance(row.get("osm_id"), str) else row.get("gml_id")
            lines.append(f"| {row.source} | {ident} | {row.get('name') or ''} | {row.h:.1f} | {row.geometry.area:,.0f} | "
                         f"{share.loc[i]:.0%} | {lat:.5f}, {lon:.5f} |")
    return lines


if __name__ == "__main__":
    import sys
    which = sys.argv[1:] or ["water", "clearance"]
    if "water" in which:
        (CHECKS / "water.md").write_text("\n".join(water()) + "\n")
    if "clearance" in which:
        (CHECKS / "clearance.md").write_text("\n".join(clearance()) + "\n")
    print((CHECKS / "water.md").read_text()[:3000])
    print((CHECKS / "clearance.md").read_text()[:4000])
