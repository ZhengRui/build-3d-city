"""Boundary change (the user, 6 Oct 13:45): the two gaps between the core and its islands become real buildings.

The district area becomes D (data/boundary_d_m3.geojson, D as M3 left it: the core, the west island with M3's Omotesando frontage, the
Asakusa-Skytree island) plus Phase 0's two gap rings (demos/data/tokyo/phase0/gaps.json: the Asakusa gap, Akihabara,
Kanda, Ueno's south, Kuramae; the west gap, Yotsuya, Shinanomachi, Aoyama, Jingu Gaien), snapped to street blocks by
snap_boundary.py's rule, NOT the masses' random ragged fringe (scripts/m3_gaps.py):
- the same OSM lines (raw/snap/snap.json: streets motorway to residential, rivers and canals, surface rail; tunnels
  out) noded with the ward boundaries and polygonized into faces (blocks) in the gaps' box + 800 m;
- a block joins when more than half of it lies inside the drawn gap ∪ D and it reaches no more than REACH m beyond
  it (no thin strips between tracks running out); faces of BIG m² or more (Shinjuku Gyoen, the Akasaka Palace
  grounds, rail yards) are cut along the drawn line;
- landmarks the brief names that the drawn rings leave out by a block or two join the same way: Ueno station and
  Ameyoko (UENO, a ring from the gap's edge up Chuo-dori to the station's north end, snapped by the same rule), and
  the block under Kanda Myojin (53 m out) and CO·MO·RE Yotsuya (60 m out) (BLOCKS);
- unioned with D, closed by 8 m and opened by 16 m (no slivers), holes under 20,000 m² filled.

Writes data/boundary_d.geojson (one feature per connected piece; piece "district"), data/boundary_districts.geojson
(each ward that the area reaches by 1,000 m² or more, clipped as snap_boundary.py does: the area cut by the ward
buffered 25 m, 6 decimals), data/districts_km2.json, data/masses_within.geojson (the rim polygons only, minus the new
area), checks/boundary.png; prints km² (all, land) per piece and ward, the snap's diff against the drawn gaps and the
[districts] block.

uv run python scripts/m3g_boundary.py   (from demos/tokyo; light, < 1 GB, ~1 min)
"""
import json
import os
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon, mapping, shape
from shapely.ops import polygonize, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from snap_boundary import water_polys  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CITY = Path(__file__).resolve().parents[1]
REPO = CITY.parents[1]
P0 = REPO / "demos/data/tokyo/phase0"
RAW = REPO / "demos/data/tokyo/raw"          # read only
UTM = "EPSG:32654"
WARDS = {"Chiyoda": 1761742, "Chuo": 1758897, "Minato": 1761717, "Koto": 3554015, "Taito": 1758888,
         "Sumida": 1758891, "Shinjuku": 1758858, "Shibuya": 1759477, "Shinagawa": 3554304,
         "Bunkyo": 1758878}           # Bunkyo: the Asakusa gap's west edge (Yushima, Ochanomizu's north bank)
REACH = 150.0
BIG = 250_000
SCRATCH = Path(os.environ.get("SNAP_SCRATCH", "/tmp"))
# Ueno's south to the station: from where the Asakusa gap's drawn west edge crosses Chuo-dori, up Chuo-dori (Ameyoko
# between it and the tracks) to Ueno Hirokoji, round the station's west side to its north end, east to the drawn edge
UENO = [(139.7713, 35.7041), (139.7713, 35.7118), (139.7745, 35.7132), (139.7760, 35.7162), (139.7887, 35.7162)]
BLOCKS = {"Kanda Myojin": (139.76789, 35.70203), "CO·MO·RE Yotsuya": (139.72906, 35.68760)}


def utm(geoms):
    return gpd.GeoSeries(geoms, crs="EPSG:4326").to_crs(UTM)


def main():
    D = gpd.read_file(CITY / "data/boundary_d_m3.geojson").to_crs(UTM).union_all()
    gaps = json.loads((P0 / "gaps.json").read_text())
    drawn = {n: utm([Polygon(g["polygon"])]).iloc[0].buffer(0) for n, g in gaps.items()}
    drawn["ueno"] = utm([Polygon(UENO)]).iloc[0].buffer(0)
    target = unary_union([D] + list(drawn.values()))
    wards = {n: utm([shape(json.loads((P0 / f"wards/{r}.geojson").read_text()))]).iloc[0].buffer(0)
             for n, r in WARDS.items()}

    osm = json.loads((RAW / "snap/snap.json").read_text())["elements"]
    lines = []
    for e in osm:
        g = e.get("geometry")
        if not g or len(g) < 2:
            continue
        t = e.get("tags", {})
        if t.get("tunnel") in ("yes", "culvert") or t.get("layer", "0").startswith("-"):
            continue
        lines.append(LineString([(p["lon"], p["lat"]) for p in g]))
    net = utm(lines)
    box = shapely.box(*unary_union(list(drawn.values())).buffer(800).bounds)
    net = net[net.intersects(box)].intersection(box)
    noded = unary_union(list(net.values) + [w.boundary.intersection(box) for w in wards.values()] + [box.boundary])
    faces = gpd.GeoSeries(list(polygonize(noded)), crs=UTM)
    faces = faces[faces.area > 1.0]
    print(f"{len(net):,} lines, {len(faces):,} faces in the gaps' box")

    add = []
    for name, d in drawn.items():
        near = faces[faces.intersects(d)]
        share = near.intersection(target).area / near.area
        big = near.area >= BIG
        out_far = near.difference(target.buffer(REACH)).area > 0.02 * near.area
        keep = list(near[~big & (share > 0.5) & ~out_far].values) + list(
            near[big | ((share > 0.5) & out_far)].intersection(target).values)
        g = unary_union(keep).difference(D)
        print(f"gap {name}: {len(keep)} blocks; drawn minus D {d.difference(D).area / 1e6:.2f} km², "
              f"snapped {g.area / 1e6:.2f} km² (+{g.difference(d).area / 1e6:.2f} beyond the drawn ring, "
              f"-{d.difference(D).difference(g).area / 1e6:.2f} of it left out); max shift "
              f"{d.difference(D).hausdorff_distance(g):.0f} m")
        add.append(g)
    for name, (lon, lat) in BLOCKS.items():
        pt = utm([shapely.Point(lon, lat)]).iloc[0]
        f = faces[faces.contains(pt)]
        f = f[f.area < BIG]
        print(f"{name}: its block {f.area.sum():,.0f} m² ({pt.distance(D.union(unary_union(add))):.0f} m out)")
        add.extend(f.values)

    p = unary_union([D] + add)
    p = p.buffer(8, join_style="mitre").buffer(-16, join_style="mitre").buffer(8, join_style="mitre")
    parts = [q for q in getattr(p, "geoms", [p]) if q.area > 20000]
    parts = [Polygon(q.exterior, [i for i in q.interiors if Polygon(i).area > 20000]).simplify(1.0) for q in parts]
    A = unary_union(parts)
    print(f"area: {len(parts)} polygon(s): " + ", ".join(f"{q.area / 1e6:.2f} km²" for q in parts)
          + f"; holes {sum(len(q.interiors) for q in parts)}")
    print(f"D {D.area / 1e6:.2f} km² -> {A.area / 1e6:.2f} km² (+{A.difference(D).area / 1e6:.2f}; "
          f"D lost {D.difference(A).area / 1e6:.4f})")

    out = gpd.GeoDataFrame({"piece": ["district"] * len(parts)}, geometry=parts, crs=UTM)
    out.to_crs("EPSG:4326").to_file(CITY / "data/boundary_d.geojson", driver="GeoJSON")

    water = water_polys()
    land = A.difference(water)
    print(f"land {land.area / 1e6:.2f} km² (D: 33.29)")

    rows, feats = [], []
    for wn, w in wards.items():
        x = w.intersection(A)
        if x.area < 1000:
            continue
        clip = A.intersection(w.buffer(25, join_style="mitre")).buffer(0)
        clip = MultiPolygon([g for g in getattr(clip, "geoms", [clip]) if g.area >= 1000])
        xp = [g for g in getattr(x, "geoms", [x]) if g.area >= 1000]
        dx = w.intersection(D).area
        rows.append((wn, WARDS[wn], x.area / 1e6, x.difference(water).area / 1e6, len(xp), dx / 1e6))
        feats.append((wn, WARDS[wn], clip))
    print("\n| District | relation | km² | land km² | parts | in D before |\n|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r[0]} | {r[1]} | {r[2]:.2f} | {r[3]:.2f} | {r[4]} | {r[5]:.2f} |")
    print(f"| all | | {sum(r[2] for r in rows):.2f} | {sum(r[3] for r in rows):.2f} | | |")
    cover = unary_union([wards[n].intersection(A) for n in wards]).area
    print(f"area covered by the wards: {cover / A.area:.4f}")
    dist = gpd.GeoDataFrame({"name": [f[0] for f in feats], "relation": [f[1] for f in feats]},
                            geometry=[f[2] for f in feats], crs=UTM).to_crs("EPSG:4326")
    dist["geometry"] = dist.geometry.set_precision(1e-6)
    (CITY / "data/boundary_districts.geojson").unlink(missing_ok=True)
    dist.to_file(CITY / "data/boundary_districts.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    json.dump([dict(zip(("district", "relation", "km2", "land_km2", "parts", "km2_before"), r)) for r in rows],
              open(CITY / "data/districts_km2.json", "w"), indent=1)
    print("\n".join(f'"{n}" = {{ relation = {r}, clip = "data/boundary_districts.geojson" }}' for n, r, _ in feats))

    # masses: the bay rim only, minus the new area
    mw = json.loads((CITY / "data/masses_within.geojson").read_text())
    keep = []
    for f in mw["features"]:
        if not f["properties"].get("rim"):
            print(f"masses: {f['properties']['name']} dropped (now real buildings)")
            continue
        g = utm([shape(f["geometry"])]).iloc[0]
        g2 = g.difference(A.buffer(1))
        g2 = MultiPolygon([q for q in getattr(g2, "geoms", [g2]) if q.area > 5000])
        print(f"masses: {f['properties']['name']} {g.area / 1e6:.2f} -> {g2.area / 1e6:.2f} km², "
              f"overlap with the area {g2.intersection(A).area:.0f} m²")
        f["properties"]["km2"] = round(g2.area / 1e6, 2)
        f["geometry"] = mapping(gpd.GeoSeries([g2], crs=UTM).to_crs("EPSG:4326").iloc[0])
        keep.append(f)
    mw["features"] = keep
    (CITY / "data/masses_within.geojson").write_text(json.dumps(mw))

    fig, ax = plt.subplots(figsize=(14, 12), dpi=110)
    gpd.GeoSeries([water], crs=UTM).plot(ax=ax, color="#cfe3f3", linewidth=0)
    for w in wards.values():
        gpd.GeoSeries([w.boundary], crs=UTM).plot(ax=ax, color="#7a5", linewidth=0.8, linestyle="--")
    gpd.GeoSeries([D], crs=UTM).plot(ax=ax, color="#99a", alpha=0.35)
    for d in drawn.values():
        gpd.GeoSeries([d.boundary], crs=UTM).plot(ax=ax, color="#e33", linewidth=1.0)
    out.boundary.plot(ax=ax, color="#113", linewidth=1.3)
    for f in keep:
        gpd.GeoSeries([shape(f["geometry"])], crs="EPSG:4326").to_crs(UTM).plot(ax=ax, color="#f90", alpha=0.4)
    x0, y0, x1, y1 = A.buffer(400).bounds
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_title("Tokyo: D (grey) + the gaps drawn (red) snapped to blocks = the district area (black); "
                 "rim masses (orange); wards (green dashed)")
    fig.savefig(CITY / "checks/boundary.png", bbox_inches="tight")
    for name, d in drawn.items():
        x0, y0, x1, y1 = d.buffer(300).bounds
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_title(f"gap {name}: drawn (red), the district area (black)")
        fig.savefig(SCRATCH / f"boundary_gap_{name}.png", bbox_inches="tight")


if __name__ == "__main__":
    main()
