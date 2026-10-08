"""M1: the band of block masses beyond Singapore's boundary (the boundary note's "Edges", decided 6 Oct 2026):
500 m of masses on the land side only (north, west and east of the centre), none on the sea sides; beyond it the
painted roofscape ([ground] town).

The band = the districts' union buffered 500 m, less the districts, less the sea. The sea is what OSM's coastline
(Phase 0's osm_coast.json, natural=coastline ways in lon 103.75-103.92, lat 1.20-1.30) leaves on its right: the
main island's coast is one open line from west to east, closed here to the north (the land side) at lat 1.45; the
islands (Sentosa, Brani, the southern islets) are closed rings. Cross-checked against URA's No-Sea subzones (the
whole of Singapore's land, coast-clipped).

Writes data/masses_within.geojson (WGS84 polygons; city.toml [ground] masses_within, the opt-in clip of branch
masses-clip) and prints its area and the share URA counts as land.
Run: uv run python scripts/m1_masses_band.py
"""
import json
from pathlib import Path

import geopandas as gpd
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import linemerge, unary_union

HERE = Path(__file__).resolve().parent.parent
DATA = HERE.parent / "data" / "singapore"
WIDTH = 500.0
NORTH = 1.45


def osm_land() -> shapely.Geometry:
    res = json.loads((DATA / "phase0" / "osm_coast.json").read_text())
    lines = [LineString([(p["lon"], p["lat"]) for p in e["geometry"]]) for e in res["elements"] if e["type"] == "way"]
    merged = linemerge(unary_union(lines))
    polys = []
    parts = sorted(getattr(merged, "geoms", [merged]), key=lambda g: -g.length)
    for i, g in enumerate(parts):
        if g.is_ring:
            polys.append(Polygon(g.coords))
        elif i == 0:                # the main island: OSM's land lies left of the way, west to east here: north
            c = list(g.coords)
            assert c[0][0] < 103.80 < 103.89 < c[-1][0], "the main coastline must run west to east across the scene"
            polys.append(Polygon(c + [(c[-1][0], NORTH), (c[0][0], NORTH)]).buffer(0))
        else:                       # an open piece cut by Phase 0's box
            print(f"  open coastline piece left out: {g.length * 111:.2f} km from {g.coords[0]} to {g.coords[-1]}")
    return unary_union(polys)


def main():
    d = gpd.read_file(HERE / "data" / "boundary_districts.geojson").to_crs(3414)
    u = d.union_all()
    land = gpd.GeoSeries([osm_land()], crs=4326).to_crs(3414).iloc[0]
    band = u.buffer(WIDTH).difference(u).intersection(land)
    band = shapely.union_all([p for p in getattr(band, "geoms", [band]) if p.area > 5000])   # crumbs under 0.5 ha
    ura = gpd.read_file(DATA / "raw" / "MP2019_subzone_nosea.geojson").to_crs(3414).union_all()
    gross = u.buffer(WIDTH).difference(u).area
    print(f"band: {band.area / 1e6:.2f} km² of {gross / 1e6:.2f} km² within {WIDTH:.0f} m "
          f"({(gross - band.area) / 1e6:.2f} km² sea dropped); URA counts {band.intersection(ura).area / band.area:.1%} "
          f"of it as land; {len(getattr(band, 'geoms', [band]))} polygons")
    out = gpd.GeoDataFrame({"name": ["masses band 500 m (land side)"]}, geometry=[band], crs=3414).to_crs(4326)
    out["geometry"] = out.geometry.simplify(0.00002)
    out.to_file(HERE / "data" / "masses_within.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)


if __name__ == "__main__":
    main()
