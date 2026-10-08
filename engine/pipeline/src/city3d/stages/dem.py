"""02_dem: fetch the elevation data the terrain is made from ([sources] dem for the ground area and
[sources] backdrop for the hills beyond it, when different), for adapters that can fetch their own data
(copernicus: the 1-degree tiles from AWS; usgs3dep: the ground area from the 3DEP image service). Adapters
without fetch() are downloaded by hand into raw/.
"""
from .. import sources
from ..common import CFG, RAW


def main():
    roles = [("ground", CFG["sources"]["dem"]), ("backdrop", CFG["sources"]["backdrop"] or CFG["sources"]["dem"])]
    for role, n in roles:
        src = sources.module(n)
        if hasattr(src, "fetch"):
            print(f"--- {role}: {n}")
            src.fetch(role)
        else:
            print(f"--- {role}: {n}: no fetch(); expecting its files in raw/")
    check()


def spots(gsrc, bsrc) -> list:
    """The DEMs at the named summits ([terrain.peaks]: the highest value within 30 m, since a summit's
    coordinates are good to a few metres) and at other named points ([terrain.spots]: the value there), with
    the surveyed or expected height where given, and what terrain.datum makes of them."""
    import numpy as np
    import rasterio
    from pyproj import Transformer
    from rasterio.windows import from_bounds
    from ..common import UTM
    to = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    shifts = sources.geotiff_shifts()
    datum = CFG["terrain"]["datum"]
    rows = [(n, v, "peak") for n, v in CFG["terrain"]["peaks"].items()] + \
           [(n, v, "spot") for n, v in CFG["terrain"].get("spots", {}).items()]
    if not rows:
        return []

    def at(paths, x0, y0, r0):
        for p in paths:
            x, y, r = x0, y0, r0          # (each raster from the UTM point: a second one in another CRS took the first's)
            with rasterio.open(p) as src:
                if src.crs is not None and src.crs.to_epsg() != int(UTM.split(":")[1]):
                    # a raster in another CRS (sources/geotiff.py: web-mercator mosaics): the point in its CRS,
                    # the radius in its units (web-mercator metres are 1/cos(lat) ground metres)
                    tx, ty = Transformer.from_crs(UTM, src.crs, always_xy=True).transform([x, x + r], [y, y])
                    x, y, r = tx[0], ty[0], abs(tx[1] - tx[0])
                if not (src.bounds.left < x < src.bounds.right and src.bounds.bottom < y < src.bounds.top):
                    continue
                cell = src.res[0]
                rr = max(r, cell)
                a = src.read(1, window=from_bounds(x - rr, y - rr, x + rr, y + rr, src.transform), masked=True)
                if a.count() == 0:
                    continue
                if shifts.get(src.name):                  # [sources.geotiff] {path, shift}
                    a = a + shifts[src.name]
                if r == 0:
                    return float(a[a.shape[0] // 2, a.shape[1] // 2])
                return float(a.max())
        return np.nan

    L = ["", f"Named points ([terrain.peaks]: highest DEM value within 30 m; [terrain.spots]: the value at the point). "
         f"Scene height = DEM − terrain.datum ({datum})." if datum != "auto" else "Named points:", "",
         "| Point | expected (m) | ground DEM (m) | backdrop DEM (m) | Δ ground − expected | scene y (m) |",
         "|---|---|---|---|---|---|"]
    for name, v, kind in rows:
        x, y = to.transform(v[0], v[1])
        r = 30.0 if kind == "peak" else 0.0
        g, b = at(gsrc.tiles("ground"), x, y, r), at(bsrc.tiles("backdrop"), x, y, r)
        exp = v[2] if len(v) > 2 else np.nan
        best = g if np.isfinite(g) else b
        sc = best - datum if datum != "auto" and np.isfinite(best) else np.nan
        f = lambda z, fmt="{:.1f}": fmt.format(z) if np.isfinite(z) else ""   # noqa: E731
        L.append(f"| {name} | {f(exp, '{:.0f}')} | {f(g)} | {f(b)} | {f(best - exp, '{:+.1f}')} | {f(sc)} |")
    return L


def extremes(r, shift=0.0, strips=False):
    """A raster's lowest and highest value with their (row, col), and its share of no data. strips ([terrain]
    dem_window): read 1024 rows at a time (Hong Kong's 2 m LiDAR mosaic and 5 m DTM whole took 2.2 GB), the
    same answer (the first cell in row order on a tie)."""
    import numpy as np
    from rasterio.windows import Window
    step = 1024 if strips else r.height
    lo = hi = None
    n_gap = 0
    for r0 in range(0, r.height, step):
        a = r.read(1, window=Window(0, r0, r.width, min(step, r.height - r0)), masked=True)
        if shift:                                        # [sources.geotiff] {path, shift}
            a += shift
        n_gap += int(np.ma.getmaskarray(a).sum())
        if a.count() == 0 and strips:
            continue
        i, j = np.unravel_index(a.argmin(), a.shape)
        if lo is None or a[i, j] < lo[0]:
            lo = (a[i, j], (r0 + i, j))
        i, j = np.unravel_index(a.argmax(), a.shape)
        if hi is None or a[i, j] > hi[0]:
            hi = (a[i, j], (r0 + i, j))
    return lo, hi, n_gap / (r.width * r.height)


def check():
    """checks/dem.md and dem.png: the ground DEM at full resolution (range, and where its extremes are), and
    against the backdrop DEM over the ground area on a 100 m grid (they must meet at the ground area's edge).
    Over the sea (a surface model such as Copernicus is exactly 0 there) the difference is that of their sea
    levels, i.e. their vertical datums; over land a surface model stands on roofs and trees, so the land
    difference is no datum offset."""
    import numpy as np
    import rasterio
    from pyproj import Transformer
    from rasterio.warp import Resampling
    from . import terrain
    from ..common import CHECKS, UTM, boundary
    ground, back = CFG["sources"]["dem"], CFG["sources"]["backdrop"] or CFG["sources"]["dem"]
    gsrc, bsrc = sources.module(ground), sources.module(back)
    L = ["# Elevation data (02_dem)", "", f"Ground: {ground}; backdrop: {back}.", ""]
    if ground == "usgs3dep":
        L += ["3DEP heights are metres over NAVD88; mean sea level at the Battery lies about 0.1 m below NAVD88 "
              "0 (NOAA station 8518750), so the scene's sea at 0 is the local mean sea level to a decimetre. "
              "The backdrop is 3DEP too, at 30 m (the ground area plus terrain.far_reach); it has no gaps over "
              "land, and its lowest values are quarry pits and bathymetry, which 05a_terrain treats as sea.", ""]
    if hasattr(gsrc, "notes"):
        L += gsrc.notes()
    to = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    shifts = sources.geotiff_shifts()
    for path in gsrc.tiles("ground"):
        with rasterio.open(path) as r:
            (lo, lo_ij), (hi, hi_ij), gap = extremes(r, shifts.get(r.name, 0.0), terrain.DEM_WINDOW)
            utm = r.crs.to_epsg() == int(UTM.split(":")[1])
            # a raster kept in its own CRS (sources/geotiff.py) is located through that CRS
            here = to if utm else Transformer.from_crs(r.crs, "EPSG:4326", always_xy=True)
            if utm or ground == "geotiff":
                for name, v, (i, j) in (("lowest", lo, lo_ij), ("highest", hi, hi_ij)):
                    x, y = r.xy(i, j)
                    lon, lat = here.transform(x, y)
                    L.append(f"- {path.name}, {name}: {v:.1f} m at {lat:.4f}, {lon:.4f}")
            L.append(f"- {path.name}: {r.width} x {r.height} pixels, {gap:.1%} no data")
    x0, y0, x1, y1 = boundary().total_bounds
    origin = ((x0 + x1) / 2, (y0 + y1) / 2)
    pad = CFG["ground"]["margin"]
    gx0, gz0, nx, nz, tr = terrain.scene_grid(origin, (x0 - pad, y0 - pad, x1 + pad, y1 + pad), 100.0)
    ga = terrain.dem_on(tr, (nz, nx), Resampling.average, gsrc.tiles("ground"))
    refs = [(back, bsrc.tiles("backdrop"))]
    cop = sorted(RAW.glob("Copernicus_DSM_COG_10_*_DEM.tif"))
    if back != "copernicus" and cop:
        refs.append(("copernicus (surface model, for reference)", cop))
    L += ["", "| Compared with the ground DEM (100 m grid over the ground area) | cells | median (m) | p10 | p90 |",
          "|---|---|---|---|---|"]
    panels = [(ga, f"ground DEM ({ground})", "terrain", None, None)]
    for name, paths in refs:
        b = terrain.dem_on(tr, (nz, nx), Resampling.average, paths)
        z = terrain.dem_on(tr, (nz, nx), Resampling.nearest, paths)
        ok = np.isfinite(ga) & np.isfinite(b)
        sea = ok & (np.abs(z) < 0.01) & (np.abs(b) < 0.05) if "copernicus" in name else ok & (b < 0.2) & (ga < 0.2)
        land = ok & (ga > 1.0)
        for label, m in (("all", ok), ("sea (the datum offset)", sea), ("land", land)):
            if m.sum():
                q = np.percentile((b - ga)[m], [50, 10, 90])
                L.append(f"| {name}, {label} | {m.sum():,} | {q[0]:+.2f} | {q[1]:+.2f} | {q[2]:+.2f} |")
        panels.append((b - ga, f"{name.split(' ')[0]} − ground (m)", "RdBu_r", -15, 15))
    if ground == "usgs3dep":
        L += ["", "Hydro-flattened water in 3DEP lies at slightly different levels per water body (about 0 to −1.6 m); "
              "05a_terrain puts all water off the land at the scene's sea level (0), so that doesn't reach the scene."]
    L += spots(gsrc, bsrc)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, len(panels), figsize=(7 * len(panels), 9), squeeze=False)
    ext = (gx0 - 50, gx0 + nx * 100 - 50, -(gz0 + nz * 100 - 50), -(gz0 - 50))
    bd = boundary().boundary.iloc[0]
    for axis, (arr, title, cmap, vmin, vmax) in zip(ax[0], panels):
        im = axis.imshow(arr, extent=ext, cmap=cmap, vmin=vmin, vmax=vmax)
        for part in getattr(bd, "geoms", [bd]):
            xy = np.asarray(part.coords)
            axis.plot(xy[:, 0] - origin[0], xy[:, 1] - origin[1], color="k", lw=0.6)
        axis.set_title(title)
        fig.colorbar(im, ax=axis, shrink=0.7)
    fig.tight_layout()
    fig.savefig(CHECKS / "dem.png", dpi=80)
    L += ["", "![dem](dem.png)"]
    (CHECKS / "dem.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
