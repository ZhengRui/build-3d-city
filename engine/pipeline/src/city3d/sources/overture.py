"""Source adapter: Overture Maps buildings (ODbL 1.0), for the heights it measured from lidar.

Overture's building theme carries OSM's footprints with a height where one is known, and records where each
property came from. Only heights whose source is USGS lidar are taken (in New Jersey: 59 % of the buildings,
where OSM has 0.3 %); those from Microsoft's ML buildings are not (they collapse on towers: a 34-storey tower
at 11 m). They are joined to the building table by OSM id, so they need OSM footprints ([sources] footprints
with "osm"). The lidar is older than some towers: where OSM's building:levels say a building is much taller
(1.5 times), the height is left to them.

[sources.overture]:
  release   the Overture release, e.g. "2026-09-23.1" (its STAC catalogue lists the GeoParquet files by bbox)
  datasets  the height sources accepted (default ["USGS Lidar"])

The heights are cached in raw/overture_heights.csv (osm_id, height, num_floors); delete it to fetch again.
Reading needs duckdb (a dependency of the engine): only the row groups inside the districts' box are read
from the one or two files covering it (tens of seconds, a few MB).
"""
import json

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

from ..common import CFG, HEADERS, RAW, boundary

C = CFG["sources"].get("overture", {})
RELEASE = C.get("release", "2026-09-23.1")
DATASETS = C.get("datasets", ["USGS Lidar"])
CACHE = RAW / "overture_heights.csv"
STAC = "https://stac.overturemaps.org/{release}/buildings/building/collection.json"
S3 = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/release/{release}/theme=buildings/type=building/"


def files(bbox) -> list:
    """The GeoParquet files whose bbox meets bbox (lon/lat)."""
    col = requests.get(STAC.format(release=RELEASE), headers=HEADERS, timeout=60).json()
    out = []
    for link in col.get("links", []):
        if link.get("rel") != "item":
            continue
        href = link["href"] if link["href"].startswith("http") else \
            STAC.format(release=RELEASE).rsplit("/", 1)[0] + "/" + link["href"].lstrip("./")
        item = requests.get(href, headers=HEADERS, timeout=60).json()
        w, s, e, n = item["bbox"]
        if w <= bbox[2] and e >= bbox[0] and s <= bbox[3] and n >= bbox[1]:
            asset = next(iter(item["assets"].values()))["href"]
            out.append(asset if asset.startswith("http") else S3.format(release=RELEASE) + asset.rsplit("/", 1)[-1])
    return out


def fetch() -> pd.DataFrame:
    import duckdb
    w, s, e, n = gpd.GeoSeries([boundary().geometry.iloc[0]], crs=boundary().crs).to_crs("EPSG:4326").total_bounds
    urls = files((w, s, e, n))
    print(f"overture: {len(urls)} file(s) cover the districts")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    rows = []
    for url in urls:
        q = f"""SELECT height, num_floors, to_json(sources) AS src FROM read_parquet('{url}')
                WHERE bbox.xmin > {w} AND bbox.xmax < {e} AND bbox.ymin > {s} AND bbox.ymax < {n}
                  AND height IS NOT NULL"""
        for height, floors, src in con.execute(q).fetchall():
            src = json.loads(src)
            osm = next((x["record_id"] for x in src if x.get("dataset") == "OpenStreetMap"), None)
            hsrc = next((x.get("dataset") for x in src if x.get("property") == "/properties/height"), None)
            if osm and hsrc in DATASETS:
                rows.append((osm.split("@")[0], float(height), floors))
    df = pd.DataFrame(rows, columns=["osm_id", "height", "num_floors"]).drop_duplicates("osm_id")
    RAW.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE, index=False)
    print(f"overture: {len(df):,} OSM buildings with a height from {', '.join(DATASETS)}")
    return df


def sample(b: gpd.GeoDataFrame) -> pd.Series:
    """The lidar height of each building by its OSM id (NaN where none, or where OSM's levels say it is
    much taller than the lidar saw: built since)."""
    df = pd.read_csv(CACHE) if CACHE.exists() else fetch()
    h = pd.Series(b.get("osm_id", pd.Series(index=b.index, dtype=object)).map(df.set_index("osm_id")["height"]),
                  index=b.index, dtype=float)
    if "h_osm_levels" in b:
        newer = b["h_osm_levels"].notna() & (b["h_osm_levels"] > 1.5 * h)
        h[newer] = np.nan
    return h
