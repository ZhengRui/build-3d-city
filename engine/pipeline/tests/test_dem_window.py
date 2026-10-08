"""terrain.dem_on's opt-ins ([terrain] dem_window: each run of DEM tiles read only over the grid it fills;
[sources.geotiff] entries {path, shift}: a vertical shift per file) and proof that without them dem_on is exactly
what it was (a frozen copy of the previous dem_on below). Synthetic tiles shaped like Hong Kong's: a fine lidar
mosaic over part of the area, then a coarser DTM over all of it, both in one projected CRS (one run), and a
geographic DEM beyond (a second run). Run: `uv run pytest tests`.
"""
import os
import subprocess
import sys
import textwrap

import numpy as np
import rasterio
from rasterio.transform import from_origin

CRS = "EPSG:2326"                        # Hong Kong 1980 Grid
E0, N0 = 830000.0, 815000.0
CITY = """
name = "windowtest"
utm_epsg = 32650
coast = true
[districts]
"Square" = 1
[paths]
data = "data"
[sources]
dem = "geotiff"
backdrop = "geotiff"
[sources.geotiff]
ground = GROUND
backdrop = ["geo_4326.tif"]
[terrain]
EXTRA
"""

OLD = '''
def old_dem_on(tr, shape, resampling, paths):
    """dem_on as it was before dem_window and shift (frozen)."""
    srcs = [rasterio.open(p) for p in paths]
    runs = []
    for s in srcs:
        if runs and runs[-1][0].crs == s.crs:
            runs[-1].append(s)
        else:
            runs.append([s])
    out = None
    for run in runs:
        if len(runs) > 1:
            gx0, gy1 = tr * (0, 0)
            gx1, gy0 = tr * (shape[1], shape[0])
            b = rasterio.warp.transform_bounds(UTM, run[0].crs, gx0, gy0, gx1, gy1)
            m = 2 * max(abs(tr.a), abs(tr.e)) * (1 if run[0].crs.is_projected else 1e-5)
            t0 = run[0].transform
            rx, ry = abs(t0.a), abs(t0.e)
            b = (t0.c + np.floor((b[0] - m - t0.c) / rx) * rx, t0.f + np.floor((b[1] - m - t0.f) / ry) * ry,
                 t0.c + np.ceil((b[2] + m - t0.c) / rx) * rx, t0.f + np.ceil((b[3] + m - t0.f) / ry) * ry)
            run = [s for s in run if s.bounds.left < b[2] and s.bounds.right > b[0]
                   and s.bounds.bottom < b[3] and s.bounds.top > b[1]]
            if not run:
                continue
        nodata = run[0].nodata
        if len(runs) > 1:
            mosaic, mtr = merge(run, bounds=b, nodata=nodata if nodata is not None else np.nan)
        else:
            mosaic, mtr = merge(run)
        src = mosaic[0].astype(np.float32)
        if nodata is not None:
            src[src == nodata] = np.nan
        part = np.zeros(shape, np.float32)
        reproject(src, part, src_transform=mtr, src_crs=run[0].crs, src_nodata=np.nan, dst_transform=tr,
                  dst_crs=UTM, resampling=resampling, dst_nodata=np.nan)
        if out is None:
            out = part
        else:
            gap = np.isnan(out)
            out[gap] = part[gap]
    for s in srcs:
        s.close()
    return out if out is not None else np.full(shape, np.nan, np.float32)
'''

PROBE = OLD + '''
import numpy as np
from pyproj import Transformer
from rasterio.warp import Resampling
from city3d.stages import terrain
from city3d.stages.terrain import *   # noqa
from city3d.common import UTM
x, y = Transformer.from_crs("EPSG:2326", UTM, always_xy=True).transform(830000 + 2500, 815000 + 2500)
res = {}
for cell, name in ((10.0, "work"), (100.0, "check")):
    _, _, nx, nz, tr = terrain.scene_grid((x, y), (x - 2200, y - 2200, x + 2200, y + 2200), cell)
    for rs in (Resampling.bilinear, Resampling.average, Resampling.nearest):
        res[f"{name}_{rs.name}_ground_new"] = terrain.dem_on(tr, (nz, nx), rs)
        res[f"{name}_{rs.name}_ground_old"] = old_dem_on(tr, (nz, nx), rs, terrain.DEM)
        res[f"{name}_{rs.name}_mixed_new"] = terrain.dem_on(tr, (nz, nx), rs, terrain.DEM + terrain.BACK)
        res[f"{name}_{rs.name}_mixed_old"] = old_dem_on(tr, (nz, nx), rs, terrain.DEM + terrain.BACK)
np.savez(OUT, **res)
'''


def _tif(path, crs, x0, y1, cell, z, nodata=-9999.0):
    with rasterio.open(path, "w", driver="GTiff", width=z.shape[1], height=z.shape[0], count=1, dtype="float32",
                       crs=crs, transform=from_origin(x0, y1, cell, cell), nodata=nodata) as r:
        r.write(z.astype(np.float32), 1)


def _city(tmp_path):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    rng = np.random.default_rng(1)
    # the coarse DTM: 5 m over 5 x 5 km, a slope with noise; the lidar: 2 m over its middle 3 x 3 km, holes in it
    j, i = np.mgrid[0:1000, 0:1000]
    _tif(raw / "dtm5.tif", CRS, E0, N0 + 5000, 5.0, 20 + i * 0.05 + rng.normal(0, 1, i.shape))
    j, i = np.mgrid[0:1500, 0:1500]
    z = 22 + i * 0.02 + rng.normal(0, 0.5, i.shape)
    z[600:700, 600:700] = -9999.0
    _tif(raw / "lidar2.tif", CRS, E0 + 1000, N0 + 4000, 2.0, z)
    # a geographic DEM round it all (1 arcsec-like)
    _tif(raw / "geo_4326.tif", "EPSG:4326", 113.9, 22.6, 0.0003, np.full((1000, 1500), 50.0))
    return raw


def _probe(tmp_path, ground, extra):
    (tmp_path / "city.toml").write_text(CITY.replace("GROUND", ground).replace("EXTRA", extra))
    out = tmp_path / f"probe{len(list(tmp_path.glob('probe*')))}.npz"
    code = "OUT = %r\n" % str(out) + textwrap.dedent(PROBE)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    r = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return dict(np.load(out))


def _pairs(d):
    return [(k[:-4], d[k], d[k[:-4] + "_old"]) for k in d if k.endswith("_new")]


def test_default_unchanged(tmp_path):
    _city(tmp_path)
    d = _probe(tmp_path, '["lidar2.tif", "dtm5.tif"]', "")
    for k, new, old in _pairs(d):
        np.testing.assert_array_equal(new, old, err_msg=k)      # NaN where NaN, else bit for bit
        assert np.isfinite(new).mean() > 0.9, k


def test_window_same_ground(tmp_path):
    _city(tmp_path)
    d = _probe(tmp_path, '["lidar2.tif", "dtm5.tif"]', "dem_window = true")
    for k, new, old in _pairs(d):
        both = np.isfinite(new) & np.isfinite(old)
        assert (np.isfinite(new) == np.isfinite(old)).all(), k
        assert np.abs(new[both] - old[both]).max() < 1e-3, (k, np.abs(new[both] - old[both]).max())


def test_shift(tmp_path):
    _city(tmp_path)
    base = _probe(tmp_path, '["lidar2.tif", "dtm5.tif"]', "")
    d = _probe(tmp_path, '[{path = "lidar2.tif", shift = -1.3}, {path = "dtm5.tif", shift = -1.3}]', "dem_window = true")
    for k, new, _ in _pairs(d):
        if "ground" not in k:
            continue
        ok = np.isfinite(new) & np.isfinite(base[k + "_new"])
        # within the lidar (away from its edge and holes, where the warp of a separate run differs) exactly -1.3
        diff = new[ok] - base[k + "_new"][ok]
        assert np.median(diff) == np.float32(-1.3) or abs(np.median(diff) + 1.3) < 1e-4, (k, np.median(diff))
