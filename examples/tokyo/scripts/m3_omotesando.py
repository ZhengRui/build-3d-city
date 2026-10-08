"""M3: extend the west island's east edge along Omotesando to the Omotesando crossing (Aoyama-dori).

M1's snapped boundary D cut Omotesando at lon 139.7085, before Omotesando Hills; Phase 0's D names Omotesando, so
the controller decided (M3) to carry the edge east along the avenue to its crossing with Aoyama-dori (~139.7125).

How (as scripts/snap_boundary.py): the same OSM lines (raw/snap/snap.json: streets, rivers, surface rail) noded with
the ward boundaries and polygonized into blocks in a small box round the avenue; the blocks that front Omotesando
(OSM ways named 表参道, from the west piece to the crossing) are those with 40 m of edge within 15 m of it whose centroid
lies within 160 m of it (not the strips between
Aoyama-dori's carriageways), big ones (15,000 m²+) cut 120 m from the centreline. They are added to the west piece (closed 8 m, as snap_boundary does), and:
- data/boundary_d.geojson: the west piece replaced;
- data/boundary_districts.geojson: each ward's clip gains the new blocks cut by the ward buffered 25 m (Shibuya's
  Jingumae, Minato's Kita- and Minami-Aoyama by the crossing);
- data/masses_within.geojson: the west gap loses them (buffered 1 m, as snap_boundary).
Prints the added area per ward. Idempotent: the blocks are recomputed and unioned (a second run adds nothing).

uv run python scripts/m3_omotesando.py   (from demos/tokyo; light: < 0.3 GB, seconds)
"""
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, MultiPolygon, Polygon, box, mapping, shape
from shapely.ops import polygonize, unary_union

CITY = Path(__file__).resolve().parents[1]
REPO = CITY.parents[1]
P0 = REPO / "demos/data/tokyo/phase0"
RAW = REPO / "demos/data/tokyo/raw"          # read only
UTM = "EPSG:32654"
WARDS = {"Shibuya": 1759477, "Minato": 1761717}
CROSSING = (139.71260, 35.66512)             # Omotesando x Aoyama-dori
DEEP = 120.0                                 # m
BOX = (139.7060, 35.6620, 139.7150, 35.6710)


def utm(geoms):
    return gpd.GeoSeries(geoms, crs="EPSG:4326").to_crs(UTM)


def main():
    osm = json.loads((RAW / "snap/snap.json").read_text())["elements"]
    lines, avenue, aoyama = [], [], []
    for e in osm:
        g = e.get("geometry")
        if not g or len(g) < 2:
            continue
        t = e.get("tags", {})
        if t.get("tunnel") in ("yes", "culvert") or t.get("layer", "0").startswith("-"):
            continue
        ls = LineString([(p["lon"], p["lat"]) for p in g])
        if not ls.intersects(box(*BOX)):
            continue
        lines.append(ls)
        if t.get("name") == "表参道" and t.get("highway"):
            avenue.append(ls)
        if t.get("name") == "青山通り" and t.get("highway"):
            aoyama.append(ls)
    wards = {n: utm([shape(json.loads((P0 / f"wards/{r}.geojson").read_text()))]).iloc[0].buffer(0)
             for n, r in WARDS.items()}
    area = utm([box(*BOX)]).iloc[0]
    net = utm(lines)
    noded = unary_union(list(net.values) + [w.boundary.intersection(area.buffer(50)) for w in wards.values()]
                        + [area.boundary])
    faces = gpd.GeoSeries(list(polygonize(noded)), crs=UTM)
    faces = faces[(faces.area > 1.0) & faces.within(area.buffer(1))]

    bd = gpd.read_file(CITY / "data/boundary_d.geojson").to_crs(UTM)
    wi = bd.index[bd["piece"] == "west"][0]
    west = bd.geometry[wi]
    cross = utm([shape({"type": "Point", "coordinates": CROSSING})]).iloc[0]
    av = unary_union(list(utm(avenue).values))
    # the avenue east of the west piece to the crossing
    av = av.difference(west.buffer(-5)).intersection(cross.buffer(1200))
    # a block fronting the avenue: 40 m or more of its edge within 15 m of the centreline (the corner blocks across
    # Aoyama-dori touch it only at the crossing), its centroid within 160 m
    front = faces.boundary.intersection(av.buffer(15)).length
    # the strips between Aoyama-dori's carriageways are not blocks
    ao = unary_union(list(utm(aoyama).values)).buffer(3)
    strip = faces.intersection(ao).area > 0.3 * faces.area
    pick = faces[(front >= 40) & (faces.centroid.distance(av) < 160) & ~strip]
    for f, fr in zip(pick, front[pick.index]):
        print(f"  block {f.area:,.0f} m², front {fr:.0f} m, centroid {f.centroid.distance(av):.0f} m off")
    # big blocks (15,000 m² and more) are cut DEEP m from the centreline (the Kita-Aoyama corner block runs 300 m up Aoyama-dori, the
    # blocks behind Omotesando Hills 150 m) are cut there: the avenue's frontage, not the hinterland
    ext = unary_union([f.intersection(av.buffer(DEEP)) if f.area > 15000 else f for f in pick])
    ext = ext.buffer(8, join_style="mitre").buffer(-8, join_style="mitre")
    # notches left between the old edge and the new blocks: blocks lying 80 % inside the union closed by 40 m
    closed = unary_union([west, ext]).buffer(40, join_style="mitre").buffer(-40, join_style="mitre")
    notch = faces[faces.intersection(closed).area > 0.8 * faces.area]
    # and what is left of a notch where the old edge cut a block (pieces under 20,000 m²)
    rest = closed.difference(unary_union([west, ext] + list(notch.values)))
    rest = [g for g in getattr(rest, "geoms", [rest]) if 200 < g.area < 20000]
    print(f"  notch blocks {len(notch)}, notch rests {len(rest)} ({sum(g.area for g in rest):,.0f} m²)")
    ext = unary_union([ext] + list(notch.values) + rest).buffer(8, join_style="mitre").buffer(-8, join_style="mitre")
    ext = ext.difference(west)
    ext = unary_union([g for g in getattr(ext, "geoms", [ext]) if g.area > 200])
    new_west = unary_union([west, ext]).buffer(8, join_style="mitre").buffer(-8, join_style="mitre")
    if isinstance(new_west, MultiPolygon):
        new_west = max(new_west.geoms, key=lambda g: g.area)
    new_west = Polygon(new_west.exterior, [i for i in new_west.interiors if Polygon(i).area > 20000]).simplify(1.0)
    added = new_west.difference(west)
    print(f"blocks picked {len(pick)}; west {west.area / 1e6:.3f} -> {new_west.area / 1e6:.3f} km² "
          f"(+{added.area / 1e6:.3f}); east edge {gpd.GeoSeries([west], crs=UTM).to_crs(4326).total_bounds[2]:.4f}"
          f" -> {gpd.GeoSeries([new_west], crs=UTM).to_crs(4326).total_bounds[2]:.4f} E")
    bd.loc[wi, "geometry"] = new_west
    bd.to_crs("EPSG:4326").to_file(CITY / "data/boundary_d.geojson", driver="GeoJSON")

    dist = gpd.read_file(CITY / "data/boundary_districts.geojson").to_crs(UTM)
    for wn, w in wards.items():
        i = dist.index[dist["name"] == wn][0]
        piece = added.buffer(0.5).intersection(w.buffer(25, join_style="mitre"))
        print(f"  {wn}: +{added.intersection(w).area / 1e6:.4f} km²")
        g = unary_union([dist.geometry[i], piece]).buffer(0)
        dist.loc[i, "geometry"] = MultiPolygon([q for q in getattr(g, "geoms", [g]) if q.area >= 1000])
    dist = dist.to_crs("EPSG:4326")
    dist["geometry"] = dist.geometry.set_precision(1e-6)
    (CITY / "data/boundary_districts.geojson").unlink()
    dist.to_file(CITY / "data/boundary_districts.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)

    mw = json.loads((CITY / "data/masses_within.geojson").read_text())
    for f in mw["features"]:
        g = utm([shape(f["geometry"])]).iloc[0]
        g2 = g.difference(new_west.buffer(1))
        if isinstance(g2, MultiPolygon):
            g2 = MultiPolygon([q for q in g2.geoms if q.area > 5000])
        if abs(g2.area - g.area) > 1:
            print(f"  gap {f['properties']['name']}: {g.area / 1e6:.2f} -> {g2.area / 1e6:.2f} km²")
        f["properties"]["km2"] = round(g2.area / 1e6, 2)
        f["geometry"] = mapping(gpd.GeoSeries([g2], crs=UTM).to_crs("EPSG:4326").iloc[0])
    (CITY / "data/masses_within.geojson").write_text(json.dumps(mw))


if __name__ == "__main__":
    main()
