"""M1: snap Phase 0's hand-drawn boundary D (plans/maps/tokyo.json, "chosen") to the streets, rivers and
railways, and cut it into the [districts] of city.toml: each ward (admin_level 7) clipped by D.

How: every OSM street (motorway to residential), river and canal centreline and surface railway in D's box
(raw/snap/snap.json, one Overpass answer), the ward boundaries and D's own outline are noded and polygonized
into faces (city blocks, and on the water side the pieces D's drawn edge closes). A face belongs to D when most
of its area lies inside the drawn polygon. So D's edges follow the nearest streets (blocks are 50-150 m here),
the Sumida's centreline where it was drawn along the river, and stay as drawn over the bay and the moats.

Writes data/boundary_d.geojson (the snapped multipolygon, one feature per piece), data/boundary_districts.geojson
(one feature per [districts] key, the ward's clip: D cut by the ward buffered 25 m; properties name, relation), data/masses_within.geojson
(Phase 0's two gaps minus D), checks/boundary.png, and prints the [districts] block for city.toml with
per-ward km² (land and water) against Phase 0's figures.

uv run python scripts/snap_boundary.py   (from demos/tokyo; light: ~0.5 GB)
"""
import json
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon, shape, mapping
from shapely.ops import polygonize, unary_union

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CITY = Path(__file__).resolve().parents[1]
REPO = CITY.parents[1]
P0 = REPO / "demos/data/tokyo/phase0"
RAW = REPO / "demos/data/tokyo/raw"
UTM = "EPSG:32654"
SCRATCH = Path(__import__("os").environ.get("SNAP_SCRATCH", "/tmp"))
WARDS = {"Chiyoda": 1761742, "Chuo": 1758897, "Minato": 1761717, "Koto": 3554015, "Taito": 1758888,
         "Sumida": 1758891, "Shinjuku": 1758858, "Shibuya": 1759477,
         "Shinagawa": 3554304}         # Shinagawa: 0.12 km² of D at Higashi-Yashio (Odaiba)
PIECES = ["core", "west", "asakusa"]          # the order of D's polygons in tokyo.json
REACH = 150.0                                  # m
BIG = 250_000                                  # m²: faces this big are cut along the drawn edge


def utm(geoms):
    return gpd.GeoSeries(geoms, crs="EPSG:4326").to_crs(UTM)


def main():
    maps = json.loads((REPO / "plans/maps/tokyo.json").read_text())
    opt = next(o for o in maps["options"] if o["id"] == maps["chosen"])
    drawn = utm([Polygon(p[0]) for p in opt["geom"]["coordinates"]])
    wards = {n: utm([shape(json.loads((P0 / f"wards/{r}.geojson").read_text()))]).iloc[0].buffer(0)
             for n, r in WARDS.items()}

    osm = json.loads((RAW / "snap/snap.json").read_text())["elements"]
    lines, kinds = [], []
    for e in osm:
        g = e.get("geometry")
        if not g or len(g) < 2:
            continue
        t = e.get("tags", {})
        if t.get("tunnel") in ("yes", "culvert") or t.get("layer", "0").startswith("-"):
            continue
        lines.append(LineString([(p["lon"], p["lat"]) for p in g]))
        kinds.append("water" if "waterway" in t else "rail" if "railway" in t else "road")
    net = utm(lines)
    box = drawn.union_all().buffer(800)
    net = net[net.intersects(box)]
    ward_lines = [w.boundary for w in wards.values()]
    noded = unary_union(list(net.values) + ward_lines + [box.envelope.boundary])
    faces = gpd.GeoSeries(list(polygonize(noded)), crs=UTM)
    faces = faces[faces.area > 1.0]
    print(f"{len(net):,} lines, {len(faces):,} faces")

    out, pieces = [], {}
    for name, d in zip(PIECES, drawn):
        near = faces[faces.intersects(d)]
        share = near.intersection(d).area / near.area
        # small faces (blocks) whole by the majority rule; big ones (the bay, the river, the palace grounds,
        # parks) cut along the drawn line
        big = near.area >= BIG
        # ... and no thin face reaching far out (the strips between parallel tracks or an elevated expressway's
        # carriageways ran 600 m out of D as spikes): a block is kept only if it lies within REACH m of the line
        out_far = near.difference(d.buffer(REACH)).area > 0.02 * near.area
        keep = list(near[~big & (share > 0.5) & ~out_far].values) + list(near[big | ((share > 0.5) & out_far)]
                                                                       .intersection(d).values)
        # closing then opening by 8 m: no slivers under 16 m wide (the strips between tracks, cut by the line)
        p = unary_union(keep).buffer(8, join_style="mitre").buffer(-16, join_style="mitre").buffer(8, join_style="mitre")
        # one polygon per piece: drop crumbs, fill pinholes the street network left
        if isinstance(p, MultiPolygon):
            p = max(p.geoms, key=lambda g: g.area)
        p = Polygon(p.exterior, [i for i in p.interiors if Polygon(i).area > 20000])
        p = p.simplify(1.0)
        pieces[name] = p
        hd = d.hausdorff_distance(p)
        far = [pt for pt in shapely.get_coordinates(p.exterior) if d.exterior.distance(shapely.Point(pt)) > 120]
        if far:
            ll = gpd.GeoSeries(shapely.points(far), crs=UTM).to_crs("EPSG:4326")
            print(f"  {name}: {len(far)} vertices over 120 m off the drawn line, e.g. "
                  + ", ".join(f"{q.y:.4f} N {q.x:.4f} E" for q in ll.iloc[::max(1, len(ll) // 4)]))
        print(f"{name}: drawn {d.area / 1e6:.2f} km², snapped {p.area / 1e6:.2f} km² "
              f"(+{p.difference(d).area / 1e6:.2f} / -{d.difference(p).area / 1e6:.2f}), "
              f"max shift {hd:.0f} m, {len(p.exterior.coords)} vertices")
        out.append(p)

    D = gpd.GeoDataFrame({"piece": list(pieces)}, geometry=list(pieces.values()), crs=UTM)
    (CITY / "data").mkdir(exist_ok=True)
    D.to_crs("EPSG:4326").to_file(CITY / "data/boundary_d.geojson", driver="GeoJSON")

    # land and water: OSM water polygons and the sea from Phase 0's coastline answer (osm_water.json)
    water = water_polys()
    Du = D.union_all()
    land = Du.difference(water) if water is not None else Du
    print(f"D snapped: {Du.area / 1e6:.2f} km² in all, {land.area / 1e6:.2f} km² land "
          f"(Phase 0: {opt['km2']} / {opt['land_km2']})")

    # districts: one per ward, its clip in data/boundary_districts.geojson (the engine's file clip: the Feature whose
    # properties.name is the district's key, a Polygon or MultiPolygon): D cut by the ward buffered 25 m, so that
    # 01_osm's relation ∩ clip = ward ∩ D even where the relation and the ward polygon saved in Phase 0 differ by a hair
    rows, feats_d = [], []
    for wn, w in wards.items():
        x = w.intersection(Du)
        if x.area < 1000:
            continue
        clip = Du.intersection(w.buffer(25, join_style="mitre")).buffer(0)
        clip = MultiPolygon([g for g in getattr(clip, "geoms", [clip]) if g.area >= 1000])
        land_ = x.difference(water).area if water is not None else x.area
        parts = [g for g in getattr(x, "geoms", [x]) if g.area >= 1000]
        rows.append((wn, WARDS[wn], x.area / 1e6, land_ / 1e6, len(parts),
                     "+".join(sorted({pn for pn, p in pieces.items() if p.intersection(w).area >= 1000}))))
        feats_d.append((wn, WARDS[wn], clip))
    print("\n| District | relation | km² | land km² | parts | pieces |\n|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r[0]} | {r[1]} | {r[2]:.2f} | {r[3]:.2f} | {r[4]} | {r[5]} |")
    print(f"| all | | {sum(r[2] for r in rows):.2f} | {sum(r[3] for r in rows):.2f} | | |")
    cover = unary_union([wards[n].intersection(Du) for n in wards]).area
    print(f"D covered by the wards: {cover / Du.area:.4f}")
    bd = gpd.GeoDataFrame({"name": [f[0] for f in feats_d], "relation": [f[1] for f in feats_d]},
                          geometry=[f[2] for f in feats_d], crs=UTM).to_crs("EPSG:4326")
    bd["geometry"] = bd.geometry.set_precision(1e-6)          # 6 decimals (0.1 m)
    (CITY / "data/boundary_districts.geojson").unlink(missing_ok=True)
    bd.to_file(CITY / "data/boundary_districts.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    json.dump([dict(zip(("district", "relation", "km2", "land_km2", "parts", "pieces"), r)) for r in rows],
              open(CITY / "data/districts_km2.json", "w"), indent=1)
    print("\n".join(f'"{n}" = {{ relation = {r}, clip = "data/boundary_districts.geojson" }}' for n, r, _ in feats_d))

    # the gaps' block masses: Phase 0's gap rings minus D
    gaps = json.loads((P0 / "gaps.json").read_text())
    feats = []
    for gname, gv in gaps.items():
        g = utm([Polygon(gv["polygon"])]).iloc[0].buffer(0).difference(Du.buffer(1))
        if isinstance(g, MultiPolygon):
            g = MultiPolygon([q for q in g.geoms if q.area > 5000])
        print(f"gap {gname}: {g.area / 1e6:.2f} km² outside D (Phase 0 {gv['km2']})")
        feats.append({"type": "Feature", "properties": {"name": gname, "km2": round(g.area / 1e6, 2)},
                      "geometry": mapping(gpd.GeoSeries([g], crs=UTM).to_crs("EPSG:4326").iloc[0])})
    (CITY / "data/masses_within.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))

    # picture
    fig, ax = plt.subplots(figsize=(14, 12), dpi=110)
    net.plot(ax=ax, color="#bbbbbb", linewidth=0.3)
    if water is not None:
        gpd.GeoSeries([water], crs=UTM).plot(ax=ax, color="#cfe3f3", linewidth=0)
    for w in wards.values():
        gpd.GeoSeries([w.boundary], crs=UTM).plot(ax=ax, color="#7a5", linewidth=0.8, linestyle="--")
    drawn.boundary.plot(ax=ax, color="#e33", linewidth=1.0)
    D.boundary.plot(ax=ax, color="#113", linewidth=1.4)
    for f in feats:
        gpd.GeoSeries([shape(f["geometry"])], crs="EPSG:4326").to_crs(UTM).plot(ax=ax, color="#f90", alpha=0.3)
    x0, y0, x1, y1 = Du.buffer(400).bounds
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_title("Tokyo D: drawn (red), snapped (black), wards (green dashed), gap masses (orange), water (blue)")
    fig.savefig(CITY / "checks/boundary.png", bbox_inches="tight")
    for name, p in pieces.items():
        x0, y0, x1, y1 = p.buffer(250).bounds
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_title(f"D {name}: drawn (red), snapped (black)")
        fig.savefig(SCRATCH / f"boundary_{name}.png", bbox_inches="tight")


def water_polys():
    """OSM water areas and the sea in D's box from Phase 0's answers (osm_water.json, osm_coast.json)."""
    try:
        w = json.loads((P0 / "osm_water.json").read_text())["elements"]
    except FileNotFoundError:
        return None
    polys = []
    for e in w:
        if e["type"] == "way" and "geometry" in e and len(e["geometry"]) >= 4:
            c = [(p["lon"], p["lat"]) for p in e["geometry"]]
            if c[0] == c[-1]:
                polys.append(Polygon(c).buffer(0))
        elif e["type"] == "relation":
            ls = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                  for m in e.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
            inner = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                     for m in e.get("members", []) if m.get("role") == "inner" and m.get("geometry")]
            o = unary_union(list(polygonize(unary_union(ls)))) if ls else None
            if o is not None and not o.is_empty:
                if inner:
                    o = o.difference(unary_union(list(polygonize(unary_union(inner)))))
                polys.append(o)
    sea = sea_poly()
    g = utm(polys).buffer(0)
    u = unary_union(list(g.values) + ([sea] if sea is not None else []))
    return u


def sea_poly():
    """The sea in D's box by the pipeline's rule (05_ground.land_from_coastline, as Phase 0's size_options.py):
    faces cut by the coastline, land on the left of the lines by a vote of probe points either side."""
    try:
        c = json.loads((P0 / "osm_coast.json").read_text())["elements"]
    except FileNotFoundError:
        return None
    from shapely.strtree import STRtree
    lu = utm([LineString([(p["lon"], p["lat"]) for p in e["geometry"]]) for e in c
              if e["type"] == "way" and len(e.get("geometry", [])) >= 2])
    area = shapely.box(*lu.union_all().envelope.bounds)
    faces = list(polygonize(unary_union(list(lu.values) + [area.exterior])))
    votes = np.zeros(len(faces))
    tree = STRtree(faces)
    for line in lu:
        cs = np.asarray(line.coords)
        mid, dd = (cs[1:] + cs[:-1]) / 2, cs[1:] - cs[:-1]
        n = np.stack([-dd[:, 1], dd[:, 0]], 1) / np.linalg.norm(dd, axis=1, keepdims=True).clip(1e-9)
        for sign in (1, -1):
            for pt in mid[::5] + sign * 2.0 * n[::5]:
                for k in tree.query(shapely.Point(pt), predicate="within"):
                    votes[k] += sign
    land = unary_union([f for f, v in zip(faces, votes) if v > 0])
    return area.difference(land)


if __name__ == "__main__":
    main()
