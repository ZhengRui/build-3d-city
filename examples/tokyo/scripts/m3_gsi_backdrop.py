"""M3 fix round: GSI's 10 m bare-earth DEM (dem_png) at z12 (~31 m pixels) for the backdrop, a mosaic in EPSG:3857.

GLO-30 is a surface model: over the western plain (Setagaya, Suginami) its roofs and trees read as lumpy hills (M3
critic). GSI's dem_png (標高タイル, the 10 m DEM, bare earth, T.P.) covers Japan's land; the sea is nodata, which
05a_terrain fills from GLO-30 (listed after it in [sources.geotiff] backdrop). No login; GSI terms (CC BY 4.0
compatible, credit 出典：国土地理院). Writes ../data/tokyo/raw/gsi_backdrop/ (tiles/, gsi_z12_mosaic.tif, README.txt).

uv run python scripts/m3_gsi_backdrop.py   (from demos/tokyo; network, ~200 tiles, light)
"""
import io
import math
import time
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_origin

CITY = Path(__file__).resolve().parents[1]
OUT = CITY.parents[0] / "data/tokyo/raw/gsi_backdrop"
Z = 12
BOX = (139.20, 35.20, 140.32, 36.22)            # the ground area + 40 km (lon0, lat0, lon1, lat1)
UA = "city3d (you@example.com)"
R = 6378137.0


def tile_xy(lon, lat):
    n = 2 ** Z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def main():
    x0, y1 = tile_xy(BOX[0], BOX[1])
    x1, y0 = tile_xy(BOX[2], BOX[3])
    nx, ny = x1 - x0 + 1, y1 - y0 + 1
    mos = np.full((ny * 256, nx * 256), np.nan, np.float32)
    got = 0
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            f = OUT / f"tiles/{Z}/{tx}/{ty}.png"
            if not f.exists():
                f.parent.mkdir(parents=True, exist_ok=True)
                url = f"https://cyberjapandata.gsi.go.jp/xyz/dem_png/{Z}/{tx}/{ty}.png"
                try:
                    data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                                  timeout=60).read()
                except urllib.error.HTTPError as e:
                    data = b"" if e.code == 404 else None
                if data is None:
                    raise RuntimeError(url)
                f.write_bytes(data)
                time.sleep(0.05)
            if f.stat().st_size == 0:
                continue
            a = np.asarray(Image.open(io.BytesIO(f.read_bytes())).convert("RGB")).astype(np.int64)
            x = a[..., 0] * 65536 + a[..., 1] * 256 + a[..., 2]
            h = np.where(x < 2 ** 23, x * 0.01, np.where(x > 2 ** 23, (x - 2 ** 24) * 0.01, np.nan)).astype(np.float32)
            mos[(ty - y0) * 256:(ty - y0 + 1) * 256, (tx - x0) * 256:(tx - x0 + 1) * 256] = h
            got += 1
    res = 2 * math.pi * R / (2 ** Z * 256)
    left = -math.pi * R + x0 * 256 * res
    top = math.pi * R - y0 * 256 * res
    with rasterio.open(OUT / "gsi_z12_mosaic.tif", "w", driver="GTiff", width=mos.shape[1], height=mos.shape[0],
                       count=1, dtype="float32", crs="EPSG:3857", transform=from_origin(left, top, res, res),
                       nodata=np.nan, compress="lzw", predictor=3, tiled=True) as r:
        r.write(mos, 1)
    print(f"{got} of {nx * ny} tiles with data; mosaic {mos.shape[1]} x {mos.shape[0]} at {res:.1f} m; "
          f"{np.isfinite(mos).mean():.0%} valid, {np.nanmin(mos):.1f} to {np.nanmax(mos):.1f} m")
    (OUT / "README.txt").write_text(f"""GSI elevation tiles dem_png (10 m DEM, bare earth, T.P.) at z{Z} for the Tokyo backdrop
Fetched {time.strftime('%d %b %Y')} by b-tokyo-m3 (scripts/m3_gsi_backdrop.py). No login.
Source: https://cyberjapandata.gsi.go.jp/xyz/dem_png/{{z}}/{{x}}/{{y}}.png (国土地理院 標高タイル)
Licence: GSI content terms (国土地理院コンテンツ利用規約), compatible with CC BY 4.0; credit "出典：国土地理院", modified.
Box: lon {BOX[0]}-{BOX[2]}, lat {BOX[1]}-{BOX[3]}; tiles x {x0}..{x1}, y {y0}..{y1} ({nx * ny}, {got} with data; 0-byte = 404).
gsi_z12_mosaic.tif: float32 m (T.P.), nodata NaN (the sea), EPSG:3857, {res:.2f} m pixels.
""")


if __name__ == "__main__":
    main()
