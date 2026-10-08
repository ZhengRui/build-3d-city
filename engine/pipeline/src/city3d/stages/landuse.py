"""05c_landuse: fetch OSM land use, which tells the facade step what a building without a useful OSM tag is for.

Writes landuse.gpkg (UTM) in the data folder, layer "landuse", one polygon per OSM area with
  use   residential, commercial, industrial or civic (schools, universities, hospitals), by [landuse] use
        (OSM "key=value" -> use)

Most buildings come from the East Asia footprints, which carry no tags, and most tall towers in
Shenzhen are apartments, so without this an office tower in Futian and an apartment tower in Bao'an
would look the same.
"""
import geopandas as gpd
from shapely.geometry import box

from ..common import CFG, DATA, UTM, boundary, element_geoms, overpass

USE = {tuple(k.split("=", 1)): v for k, v in CFG["landuse"]["use"].items()}   # (key, value) -> use


def main():
    area = box(*boundary().total_bounds)
    s, w, n, e = gpd.GeoSeries([area], crs=UTM).to_crs("EPSG:4326").total_bounds[[1, 0, 3, 2]]
    landuse = "|".join(v for k, v in USE if k == "landuse")
    amenity = "|".join(v for k, v in USE if k == "amenity")
    res = overpass(f"""
        [out:json][timeout:900][bbox:{s:.5f},{w:.5f},{n:.5f},{e:.5f}];
        (
          way["landuse"~"^({landuse})$"]; rel["landuse"~"^({landuse})$"];
          way["amenity"~"^({amenity})$"]; rel["amenity"~"^({amenity})$"];
        );
        out geom;
    """)
    rows = []
    for t, g in element_geoms(res):
        use = next((u for (k, v), u in USE.items() if t.get(k) == v), None)
        if use and g.geom_type in ("Polygon", "MultiPolygon"):
            rows.append({"use": use, "name": t.get("name"), "geometry": g})
    lu = gpd.GeoDataFrame(rows, crs="EPSG:4326").to_crs(UTM)
    lu["geometry"] = lu.geometry.make_valid()
    lu = lu[lu.intersects(boundary().geometry.iloc[0])]
    out = DATA / "landuse.gpkg"
    out.unlink(missing_ok=True)
    lu.to_file(out, layer="landuse")
    km2 = lu.assign(km2=lu.area / 1e6).groupby("use").km2.sum()
    print(f"{len(lu):,} areas; km² by use:\n{km2.round(1).to_string()}")

