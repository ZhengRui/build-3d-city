"""M3 fix round: a waterfront rim of block masses (the user's decision, 6 Oct 12:00): Toyosu (1-6 chome, the
reclaimed island with its towers and the market), Ariake (1-3 chome, Big Sight and the Ariake towers) and Shibaura
(1-4 chome's waterfront and the Konan / Shinagawa wharf strip along the Keihin canal facing Odaiba), added to
data/masses_within.geojson beside the two gaps.

Each area is drawn roughly here (lon, lat rings) and snapped: the OSM street blocks (raw/osm_roads.json, as
scripts/m3_gaps.py) more than half inside the drawn ring, cut to the land (05_ground's land less its water: the canals
and the bay give the islands their own edges), less D (buffered 1 m). Idempotent: features of these names replaced.

uv run python scripts/m3_rim.py   (from demos/tokyo, after 05_ground; light)
"""
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, MultiPolygon, Polygon, box, mapping
from shapely.ops import polygonize, unary_union

CITY = Path(__file__).resolve().parents[1]
DATA = CITY.parents[0] / "data/tokyo"
UTM = "EPSG:32654"
BIG = 40_000
KINDS = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "motorway_link",
         "trunk_link", "primary_link", "secondary_link", "tertiary_link", "service"}
RIM = {
    "toyosu": [(139.7820, 35.6610), (139.7940, 35.6625), (139.8030, 35.6560), (139.7990, 35.6460),
               (139.7880, 35.6395), (139.7790, 35.6440)],
    "ariake": [(139.7800, 35.6395), (139.7940, 35.6405), (139.8010, 35.6330), (139.7985, 35.6235),
               (139.7855, 35.6240), (139.7790, 35.6300)],
    "shibaura": [(139.7470, 35.6530), (139.7590, 35.6510), (139.7640, 35.6420), (139.7570, 35.6320),
                 (139.7530, 35.6170), (139.7430, 35.6140), (139.7410, 35.6300), (139.7430, 35.6460)],
}


def main():
    D = gpd.read_file(CITY / "data/boundary_d.geojson").to_crs(UTM).union_all()
    land = gpd.read_file(DATA / "ground.gpkg", layer="land").to_crs(UTM).union_all()
    water = gpd.read_file(DATA / "ground.gpkg", layer="water").to_crs(UTM).make_valid().union_all()
    dry = land.difference(water)
    osm = json.loads((DATA / "raw/osm_roads.json").read_text())["elements"]
    lines = [LineString([(p["lon"], p["lat"]) for p in e["geometry"]]) for e in osm
             if e.get("geometry") and len(e["geometry"]) > 1 and e.get("tags", {}).get("highway") in KINDS
             and e.get("tags", {}).get("tunnel") not in ("yes",) and not e.get("tags", {}).get("bridge")]
    net = gpd.GeoSeries(lines, crs="EPSG:4326").to_crs(UTM)
    mw = json.loads((CITY / "data/masses_within.geojson").read_text())
    mw["features"] = [f for f in mw["features"] if f["properties"]["name"] not in RIM]
    for name, ring in RIM.items():
        drawn = gpd.GeoSeries([Polygon(ring)], crs="EPSG:4326").to_crs(UTM).iloc[0]
        area = box(*drawn.buffer(400).bounds)
        sub = net[net.intersects(area)].intersection(area)
        faces = gpd.GeoSeries(list(polygonize(unary_union(list(sub.values) + [area.boundary]))), crs=UTM)
        faces = faces[faces.area > 50]
        share = faces.intersection(drawn).area / faces.area
        big = faces.area >= BIG               # superblocks (the market, Big Sight, wharves) cut along the drawn line
        keep = faces[~big & (share > 0.5)]
        g = unary_union(list(keep.values) + list(faces[big].intersection(drawn).values)).intersection(dry).difference(D.buffer(1))
        g = g.buffer(1, join_style="mitre").buffer(-1, join_style="mitre")
        g = MultiPolygon([q for q in getattr(g, "geoms", [g]) if q.geom_type == "Polygon" and q.area > 5000])
        print(f"rim {name}: drawn {drawn.area / 1e6:.2f} km², snapped {g.area / 1e6:.2f} km² ({len(keep)} blocks)")
        mw["features"].append({"type": "Feature", "properties": {"name": name, "km2": round(g.area / 1e6, 2),
                                                                 "rim": True},
                               "geometry": mapping(gpd.GeoSeries([g.simplify(1.0)], crs=UTM).to_crs(4326).iloc[0])})
    (CITY / "data/masses_within.geojson").write_text(json.dumps(mw))


if __name__ == "__main__":
    main()
