"""Hong Kong M3: the 2020 LiDAR's excavations under buildings finished since, as terrain patches.

scripts/m2_landsd_prep.py flags the LandsD rows whose lowest LiDAR ground is under 1 mPD (`pit`: Kai Tak's Monaco and
The Henley, Grand Victoria, NCB Innovation Centre, The Twins; down to -18 mPD) and stands them on the street around
them (`ground_mpd`). Here the excavation itself is found in the 2 m LiDAR: the cells lying PIT_DEPTH m or more under
that street level, connected to the row's footprint and within REACH m of it. The union, grown GROW m so its outline
lies on the street, is written as data/m3_pits.geojson (WGS84), which 05a_terrain re-fills from its outline
([terrain] patches_file). The generic [terrain] pits rule can't be used here: on the island's steep slopes its
closing-based growth spread over every valley (1,362 "pits", 13,817 ha, up to 187 m raised).

Run from demos/hongkong after m2_landsd_prep (reads LiDAR windows only, ~0.3 GB):
    uv run python scripts/m3_pits.py
"""
import json

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.features
import shapely
from rasterio.windows import from_bounds
from scipy import ndimage as ndi

from city3d.common import CITY, DATA

PD_TO_MSL = 1.30
LIDAR = DATA / "dem_prepared/lidar2020_dtm_2m_msl.tif"
ROWS = DATA / "landsd_prepared/landsd_E600_ground.gpkg"
OUT = CITY / "data/m3_pits.geojson"
PIT_DEPTH = 1.5      # m under the street level round the row
REACH = 150.0        # m from the row's outline
GROW = 6.0           # m: the patch's outline on the street, beyond the excavation's lip


def main():
    g = gpd.read_file(ROWS, columns=["pit", "ground_mpd", "ground_lidar_mpd", "BuildingNameEN"])
    g = g[g["pit"].astype(bool)]
    print(f"{len(g)} pit rows")
    polys, deep = [], []
    with rasterio.open(LIDAR) as r:
        for _, row in g.iterrows():
            x0, y0, x1, y1 = row.geometry.buffer(REACH).bounds
            win = from_bounds(x0, y0, x1, y1, r.transform).round_offsets().round_lengths()
            a = r.read(1, window=win, masked=True).astype(np.float32).filled(np.nan)
            if a.size == 0:
                continue
            tr = r.window_transform(win)
            street = row["ground_mpd"] - PD_TO_MSL
            low = np.nan_to_num(a, nan=1e9) < street - PIT_DEPTH
            near = rasterio.features.geometry_mask([row.geometry.buffer(REACH)], a.shape, tr, invert=True)
            foot = rasterio.features.geometry_mask([row.geometry.buffer(2.0)], a.shape, tr, invert=True)
            lab, n = ndi.label(low & near, structure=np.ones((3, 3), bool))
            keep = np.unique(lab[foot & (lab > 0)])
            if not len(keep):
                continue
            m = np.isin(lab, keep)
            deep.append(float(street - np.nanmin(a[m])))
            for geom, v in rasterio.features.shapes(m.astype(np.uint8), mask=m, transform=tr):
                polys.append(shapely.geometry.shape(geom))
    u = shapely.union_all(polys).buffer(GROW).buffer(-2.0).simplify(2.0)
    parts = [p for p in getattr(u, "geoms", [u]) if p.area >= 50]
    s = gpd.GeoSeries(parts, crs="EPSG:2326")
    print(f"{len(parts)} patches, {s.area.sum() / 1e4:.1f} ha, deepest {max(deep):.1f} m under its street "
          f"(median {np.median(deep):.1f}) from {len(deep)} rows")
    ll = s.to_crs(4326)
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"area_m2": round(float(a))},
         "geometry": json.loads(shapely.to_geojson(shapely.set_precision(p, 1e-7)))}
        for p, a in zip(ll, s.area)]}
    OUT.write_text(json.dumps(fc))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
