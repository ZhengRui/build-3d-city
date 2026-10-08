"""Source adapter: the USGS 3D Elevation Program (3DEP) bare-earth DEM, for the United States.

3DEP is a seamless mosaic of the best elevation the USGS holds, mostly lidar at 1 m in cities (NYC's 2017
lidar among them), heights over NAVD88 in metres, public domain. It is bare earth: buildings and trees are
already taken out and water is hydro-flattened, so the terrain stage skips its building masking, opening and
canopy steps (BARE) and only smooths lightly.

No tiles to download by hand: fetch() (stage 02_dem) asks the 3DEPElevation ImageServer's exportImage for the
ground area plus a kilometre, resampled to [sources.usgs3dep] cell metres in the city's UTM zone (at most
8000 x 8000 pixels per request), and keeps it as raw/usgs3dep.tif. As the backdrop's DEM ([sources] backdrop =
"usgs3dep") it fetches the ground area plus terrain.far_reach at back_cell metres (raw/usgs3dep_backdrop.tif):
bare earth in the same datum as the ground, so the backdrop has no towns baked in as lumps (a surface model's
do) and meets the ground without a step. Beyond the coast it has no data, which the backdrop reads as sea.
"""
import numpy as np
import rasterio
import requests

from ..common import CFG, HEADERS, RAW, UTM_EPSG, boundary

URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
C = CFG["sources"]["usgs3dep"]
FILES = {"ground": RAW / "usgs3dep.tif", "backdrop": RAW / "usgs3dep_backdrop.tif"}
BARE = True
BLOCK = 2000                # pixels per request side


def tiles(role: str = "ground") -> list:
    return [FILES[role]]


def extent(role: str = "ground") -> tuple:
    """(west, south, east, north) in degrees covered by the file."""
    import rasterio.warp
    with rasterio.open(FILES[role]) as r:
        w, s, e, n = rasterio.warp.transform_bounds(r.crs, "EPSG:4326", *r.bounds)
    return float(w), float(s), float(e), float(n)


def fetch(role: str = "ground"):
    FILE = FILES[role]
    if FILE.exists():
        print(f"{FILE.name}: already here")
        return
    pad = CFG["ground"]["margin"] + (1000.0 if role == "ground" else CFG["terrain"]["far_reach"] + 2000.0)
    x0, y0, x1, y1 = boundary().total_bounds
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    cell = C["cell"] if role == "ground" else C["back_cell"]
    w, h = int(np.ceil((x1 - x0) / cell)), int(np.ceil((y1 - y0) / cell))
    x1, y1 = x0 + w * cell, y0 + h * cell
    print(f"3DEP {role}: {w} x {h} pixels at {cell} m ...", flush=True)
    # in blocks: one big request makes the service answer 500
    out = np.full((h, w), -9999.0, np.float32)
    for r0 in range(0, h, BLOCK):
        for c0 in range(0, w, BLOCK):
            bh, bw = min(BLOCK, h - r0), min(BLOCK, w - c0)
            bx0, by1 = x0 + c0 * cell, y1 - r0 * cell
            out[r0:r0 + bh, c0:c0 + bw] = block(bx0, by1 - bh * cell, bx0 + bw * cell, by1, bw, bh)
    RAW.mkdir(parents=True, exist_ok=True)
    tr = rasterio.transform.from_origin(x0, y1, cell, cell)
    with rasterio.open(FILE, "w", driver="GTiff", width=w, height=h, count=1, dtype="float32", crs=f"EPSG:{UTM_EPSG}",
                       transform=tr, nodata=-9999.0, compress="deflate", predictor=3, tiled=True) as dst:
        dst.write(out, 1)
    ok = out > -9000
    print(f"{FILE.name}: {w} x {h}, heights {out[ok].min():.1f}..{out[ok].max():.1f} m, {1 - ok.mean():.1%} no data")


def block(x0, y0, x1, y1, w, h, tries=6):
    """One exportImage request, as an array (no data -9999)."""
    import io
    import time
    params = {"bbox": f"{x0},{y0},{x1},{y1}", "bboxSR": UTM_EPSG, "imageSR": UTM_EPSG, "size": f"{w},{h}",
              "format": "tiff", "pixelType": "F32", "noData": -9999, "noDataInterpretation": "esriNoDataMatchAny",
              "interpolation": "RSP_BilinearInterpolation", "f": "image"}
    for k in range(tries):
        try:
            r = requests.get(URL, params=params, headers=HEADERS, timeout=600)
            r.raise_for_status()
            if not r.content.startswith((b"II*", b"MM\x00*")):
                raise RuntimeError(f"3DEP answered {r.headers.get('content-type')}: {r.content[:200]!r}")
            with rasterio.open(io.BytesIO(r.content)) as src:
                a = src.read(1).astype(np.float32)
                if src.nodata is not None:
                    a[a == src.nodata] = -9999.0
            return a
        except (requests.RequestException, RuntimeError) as e:
            if k == tries - 1:
                raise
            print(f"  retry after: {e}", flush=True)
            time.sleep(10 * (k + 1))
