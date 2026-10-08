"""Source adapter: official building footprints from an ArcGIS REST FeatureServer layer (stage 02_arcgis).

Many cities publish their building layer as an ArcGIS feature service besides (or instead of) a download
portal: New York City's BUILDING layer (NYC OTI, the same data as NYC Open Data's "Building Footprints",
with the roof height of every building above its ground, in feet), and state and county GIS the same way.
A service that can be reached when the portal can't (NYC Open Data answers 403 outside the US) is often the
simplest way in.

[sources.arcgis] says which layer and how to read it:
  url           the layer (.../FeatureServer/<n>)
  where         an SQL filter, e.g. "BIN >= 1000000 AND BIN < 2000000" (Manhattan's buildings); "1=1": all
  drop          {FIELD = [values]}: features left out (NYC: FEATURE_CODE 2110 skybridge, 1003 placeholder
                triangle, 1005 temporary structure)
  height        the field with the roof height above the building's ground ("": none)
  height_scale  its unit in metres (0.3048 for feet)
  keep          further fields copied into the table (lower-cased), e.g. BIN, CONSTRUCTION_YEAR, NAME
  join          optional: attributes of another layer joined on a key, without its geometry, e.g. NYC's
                MapPLUTO lots (building class, floors, land use, year) on the footprints' MAPPLUTO_BBL:
                {url, where, key (its field), on (the footprints' field, lower-cased), fields}; cached in
                raw/arcgis_join.json
The layer is read in pages (resultOffset) within the districts' bounding box, clipped to the districts and
cached whole in raw/arcgis.geojson (delete it to fetch again).

Role in the building table (04_buildings): "primary", authoritative footprints of every building, chosen
before OSM's (OSM fills what they lack); HEIGHTS: its height field, the "arcgis" height source.

Writes arcgis_buildings.gpkg (WGS84) in the data folder.
"""
import json
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

from ..common import CFG, DATA, HEADERS, RAW, UTM, boundary

STAGE = "02_arcgis"
ROLE = "primary"
C = CFG["sources"]["arcgis"]
HEIGHTS = bool(C["height"])
PAGE = 2000
CACHE = RAW / "arcgis.geojson"


def load() -> gpd.GeoDataFrame:
    g = gpd.read_file(DATA / "arcgis_buildings.gpkg").to_crs(UTM)
    g["geometry"] = g.geometry.make_valid()
    return g


def _get(url: str, params: dict, tries: int = 6) -> dict:
    for k in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=180)
            r.raise_for_status()
            res = r.json()
            if "error" in res:
                raise requests.RequestException(str(res["error"])[:300])
            return res
        except (requests.RequestException, json.JSONDecodeError) as e:
            if k == tries - 1:
                raise
            print(f"  retry after: {e}")
            time.sleep(5 * (k + 1))


def fetch(bbox) -> dict:
    """Every feature of the layer matching `where` within the bbox (lon/lat), as one GeoJSON collection."""
    q = C["url"].rstrip("/") + "/query"
    base = {"where": C["where"], "geometry": ",".join(f"{v:.6f}" for v in bbox), "geometryType": "esriGeometryEnvelope",
            "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outSR": 4326}
    n = _get(q, {**base, "returnCountOnly": "true", "f": "json"})["count"]
    print(f"{C['url']}: {n:,} features")
    feats = []
    for off in range(0, n, PAGE):
        res = _get(q, {**base, "outFields": "*", "orderByFields": "OBJECTID", "resultOffset": off,
                       "resultRecordCount": PAGE, "f": "geojson"})
        feats += res["features"]
        print(f"  {len(feats):,} / {n:,}", flush=True)
    if len(feats) < n:
        raise RuntimeError(f"only {len(feats)} of {n} features came back")
    return {"type": "FeatureCollection", "features": feats}


def fetch_table(url: str, where: str, fields: list) -> list:
    """The attributes of every feature of a layer matching `where`, no geometry."""
    q = url.rstrip("/") + "/query"
    n = _get(q, {"where": where, "returnCountOnly": "true", "f": "json"})["count"]
    rows = []
    for off in range(0, n, PAGE):
        res = _get(q, {"where": where, "outFields": ",".join(fields), "returnGeometry": "false",
                       "orderByFields": "OBJECTID", "resultOffset": off, "resultRecordCount": PAGE, "f": "json"})
        rows += [f["attributes"] for f in res["features"]]
    print(f"{url}: {len(rows):,} of {n:,} rows")
    return rows


def join(out: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    J = C.get("join") or {}
    if not J:
        return out
    cache = RAW / "arcgis_join.json"
    if not cache.exists():
        cache.write_text(json.dumps(fetch_table(J["url"], J["where"], [J["key"], *J["fields"]])))
    t = pd.DataFrame(json.loads(cache.read_text()))
    key = pd.to_numeric(t[J["key"]], errors="coerce").astype("Int64").astype(str)
    t = t.drop(columns=[J["key"]]).set_axis([f.lower() for f in J["fields"]], axis=1).assign(_k=key.values)
    t = t.drop_duplicates("_k").set_index("_k")
    on = pd.to_numeric(out[J["on"]], errors="coerce").astype("Int64").astype(str)
    for c in t.columns:
        out[c] = on.map(t[c]).values
    print(f"join: {on.isin(t.index).mean():.1%} of the footprints found in {J['url'].split('/services/')[-1]}")
    return out


def main():
    bd = boundary()
    if not CACHE.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(fetch(bd.to_crs(4326).total_bounds)))
    g = gpd.read_file(CACHE)
    n0 = len(g)
    for field, values in C["drop"].items():
        g = g[~g[field].isin(values)]
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    g = g[g.to_crs(UTM).intersects(bd.geometry.iloc[0])].copy()
    out = gpd.GeoDataFrame({k.lower(): g[k].values for k in C["keep"] if k in g}, geometry=g.geometry.values,
                           crs="EPSG:4326")
    if HEIGHTS:
        h = pd.to_numeric(g[C["height"]], errors="coerce").values * C["height_scale"]
        out["h"] = np.where(h > 0, h, np.nan)          # 0 or empty: not known
    out["source"] = "official"
    out = join(out)
    out.to_file(DATA / "arcgis_buildings.gpkg")
    print(f"official footprints: {n0:,} fetched, {len(out):,} in the districts after dropping "
          f"{ {k: v for k, v in C['drop'].items()} }; with height: {out['h'].notna().sum() if HEIGHTS else 0:,}")
    if HEIGHTS:
        print(out["h"].describe().round(1).to_string())
