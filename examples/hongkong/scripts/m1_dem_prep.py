"""M1: Hong Kong's official terrain prepared for 05a_terrain's geotiff adapter (no engine change).

Two reasons the raw files can't be listed in [sources.geotiff] as they are:
1. the CEDD 2020 LiDAR DTM is 0.5 m: 05a_terrain's dem_on() merges its tiles at their own resolution before
   warping (rasterio.merge without res), which for the ground area (E + 3 km, ~550 km²) is ~2.2e9 cells, ~9 GB
   twice over: an OOM on this 15 GB machine. Resampled here to 2 m (cell average) in EPSG:2326: 80 M cells.
2. both DTMs are in metres above Principal Datum (mPD), which lies ~1.2-1.4 m under mean sea level; the scene's
   sea is at 0 = mean sea level, and the engine has a backdrop shift (terrain.back_shift) but no ground shift for a
   coastal city (terrain.datum is inland-only). The offset is taken off here: scene height = mPD - PD_TO_MSL.

Writes demos/data/hongkong/dem_prepared/{lidar2020_dtm_2m_msl.tif, dtm5m_msl.tif} (EPSG:2326, float32,
nodata -9999, LZW, tiled). Usage: uv run python scripts/m1_dem_prep.py [--offset 1.3] [--res 2]"""
import argparse
import glob
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.enums import Resampling

DATA = Path(__file__).resolve().parents[2] / "data/hongkong"
OUT = DATA / "dem_prepared"
ap = argparse.ArgumentParser()
ap.add_argument("--offset", type=float, default=1.3, help="m: mean sea level above Principal Datum")
ap.add_argument("--res", type=float, default=2.0)
ap.add_argument("--only", choices=["lidar", "dtm5m"], default=None)
a = ap.parse_args()
OUT.mkdir(parents=True, exist_ok=True)
prof = dict(driver="GTiff", dtype="float32", nodata=-9999.0, compress="lzw", tiled=True, blockxsize=512,
            blockysize=512, predictor=3, crs="EPSG:2326", BIGTIFF="IF_SAFER")


def write(path, arr, tr):
    arr = np.where(np.isfinite(arr) & (arr > -9000), arr - a.offset, -9999.0).astype(np.float32)
    with rasterio.open(path, "w", height=arr.shape[0], width=arr.shape[1], count=1, transform=tr, **prof) as d:
        d.write(arr, 1)
        d.update_tags(note=f"m above mean sea level = mPD - {a.offset}", source="see raw/*/README.txt")
    ok = arr > -9000
    print(f"{path.name}: {arr.shape[1]} x {arr.shape[0]} cells, {ok.mean() * 100:.1f} % data, "
          f"{np.nanmin(arr[ok]):.1f} to {np.nanmax(arr[ok]):.1f} m", flush=True)


if a.only in (None, "lidar"):
    t0 = time.time()
    zips = sorted(glob.glob(str(DATA / "raw/dtm_lidar/tiles/*.zip")))
    paths = []
    for z in zips:
        import zipfile
        with zipfile.ZipFile(z) as zf:
            paths += [f"/vsizip/{z}/{n}" for n in zf.namelist() if n.lower().endswith(".tif")]
    srcs = [rasterio.open(p) for p in paths]
    mosaic, tr = merge(srcs, res=a.res, resampling=Resampling.average, nodata=-9999.0, dtype="float32")
    for s in srcs:
        s.close()
    print(f"lidar: {len(zips)} tiles merged at {a.res} m ({time.time() - t0:.0f} s)", flush=True)
    write(OUT / f"lidar2020_dtm_{a.res:g}m_msl.tif", mosaic[0], tr)
    del mosaic

if a.only in (None, "dtm5m"):
    t0 = time.time()
    with rasterio.open(DATA / "raw/dtm5m/Whole_HK_DTM_5m.asc") as s:
        arr, tr = s.read(1).astype(np.float32), s.transform
        nd = s.nodata
    arr[arr == nd] = np.nan
    # the 5 m DTM writes 0, not nodata, over the sea (its first rows are all 0): keep 0 as data (it is sea level
    # in mPD, so -offset after the shift, which the terrain's coastline rule overrides anyway)
    print(f"dtm5m read ({time.time() - t0:.0f} s)", flush=True)
    write(OUT / "dtm5m_msl.tif", arr, tr)
