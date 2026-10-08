"""M3 fix round: the gaps' mass polygons (data/masses_within.geojson) snapped to street blocks.

Phase 0 drew the two gaps as straight-sided rings: the Asakusa gap read as a trapezoid with dead-straight sides (its
west edge on the JR Ueno line), the west gap stopped on straight lines north of Yotsuya (M3 critic). Each gap is
replaced by the OSM street blocks (05b_roads' cached Overpass answer raw/osm_roads.json: highways down to
residential, surface railways; tunnels left out, polygonized in the gap's box + 600 m) that lie more than half inside
it, minus D (buffered 1 m, as snap_boundary.py); across an 800 m band centred on the drawn outer edges (not those on D)
blocks are kept at random, more surely the deeper inside they lie (half on the line: the area stays about the same) (a ragged fringe: the critic's straight "light cone"). Blocks over 0.25 km² (the Imperial Palace's grounds, Shinjuku Gyoen,
rail yards) are cut along the drawn line as snap_boundary does. Prints each gap's area before and after.

uv run python scripts/m3_gaps.py   (from demos/tokyo, after 05b_roads; light, < 1 GB)
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, MultiPolygon, box, mapping, shape
from shapely.ops import polygonize, unary_union

CITY = Path(__file__).resolve().parents[1]
DATA = CITY.parents[0] / "data/tokyo"
UTM = "EPSG:32654"
KINDS = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "motorway_link",
         "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
BIG = 250_000
FRAY = 800.0


def main():
    D = gpd.read_file(CITY / "data/boundary_d.geojson").to_crs(UTM).union_all()
    mw = json.loads((CITY / "data/masses_within.geojson").read_text())
    osm = json.loads((DATA / "raw/osm_roads.json").read_text())["elements"]
    lines = []
    for e in osm:
        t, g = e.get("tags", {}), e.get("geometry")
        if not g or len(g) < 2 or t.get("tunnel") in ("yes", "building_passage") or t.get("layer", "0").startswith("-"):
            continue
        if t.get("highway") in KINDS or (t.get("railway") in ("rail", "subway", "light_rail") and not t.get("bridge")):
            lines.append(LineString([(p["lon"], p["lat"]) for p in g]))
    net = gpd.GeoSeries(lines, crs="EPSG:4326").to_crs(UTM)
    for f in mw["features"]:
        gap = gpd.GeoSeries([shape(f["geometry"])], crs="EPSG:4326").to_crs(UTM).iloc[0]
        area = box(*gap.buffer(600).bounds)
        sub = net[net.intersects(area)].intersection(area)
        faces = gpd.GeoSeries(list(polygonize(unary_union(list(sub.values) + [area.boundary]))), crs=UTM)
        faces = faces[faces.area > 50]
        share = faces.intersection(gap).area / faces.area
        big = faces.area >= BIG
        # across a FRAY m band centred on the drawn line's outer edges (not the edges on D) blocks are kept at random,
        # surer the deeper inside they lie: a ragged fringe instead of a straight edge, about the same area
        outer = gap.boundary.difference(D.buffer(40))
        rp = faces.representative_point()
        sd = np.where(rp.within(gap), 1, -1) * rp.distance(outer).to_numpy()    # + inside, - outside
        rng = np.random.default_rng(11)
        p = np.clip((sd + FRAY / 2) / FRAY, 0, 1)
        kept = ~big & (rng.random(len(faces)) < p) & ~rp.within(D.buffer(1))
        keep = list(faces[kept].values) + list(faces[big].intersection(gap).values)
        g = unary_union(keep).buffer(2, join_style="mitre").buffer(-2, join_style="mitre").difference(D.buffer(1))
        g = MultiPolygon([q for q in getattr(g, "geoms", [g]) if q.area > 5000])
        print(f"gap {f['properties']['name']}: {gap.area / 1e6:.2f} -> {g.area / 1e6:.2f} km² "
              f"({len(keep)} blocks)")
        f["properties"]["km2"] = round(g.area / 1e6, 2)
        f["geometry"] = mapping(gpd.GeoSeries([g.simplify(1.0)], crs=UTM).to_crs("EPSG:4326").iloc[0])
    (CITY / "data/masses_within.geojson").write_text(json.dumps(mw))


if __name__ == "__main__":
    main()
