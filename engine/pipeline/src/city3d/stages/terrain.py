"""05a_terrain: a plausible bare-earth ground under the scene, and the hills around it, from the Copernicus DEM
(the DEM source adapter, [sources] dem). Parameters are [terrain]'s; as built for Shenzhen:

Until now the city stood on a plane (land at y = 0, the sea plane at -1). Western Shenzhen is anything but
flat: 大南山 and 小南山 over Shekou, 塘朗山 and the hills round 西丽水库 behind Nanshan, 羊台山 (587 m) on the
northern edge, 凤凰山 and 铁仔山 in Bao'an, 莲花山 and 笔架山 in Futian, and the plain itself climbs gently
inland to the 西丽 and 石岩 basins; across the bay stand the hills of the New Territories and Lantau.

The Copernicus GLO-30 DEM (raw/Copernicus_DSM_COG_10_*: 1 arcsecond, heights over EGM2008) is a surface
model: in the city it is the roofs, on the hills the forest canopy. The ground under it is estimated on a
WORK m grid over the ground area (05_ground.py's extent):
  buildings   footprints (buildings.gpkg, grown by BUILDING_PAD, as the DEM's 30 m pixels smear them) are
              masked and the rest opened (a minimum, then a maximum filter over OPEN m): whatever is
              narrower goes (unmapped buildings in Hong Kong and beyond the districts, single trees);
              masked blocks take the opening over ever larger windows
  canopy      CANOPY metres per OSM green class (08_trees.py's cached areas), blurred, taken off. The DEM's
              summits are within a few metres of the surveyed heights (crests carry scrub rather than
              forest), so the allowance is modest; the viewer's trees stand on top again
  smoothing   SMOOTH_OPEN on open ground and hills, SMOOTH_TOWN where built up (the DEM there is roofs)
  sea level   reclaimed land and the coastal plain lie a few metres above the sea, but the scene's land
              meets the sea plane at 0: the ground drops by SEA_DROP with a soft knee of SEA_KNEE (nothing
              below 0), is exactly 0 within COAST_FLAT of the sea and rises to its own height over COAST_RAMP.
              An inland city (city.toml coast = false, or "auto" and no sea in the ground area) has no sea
              to meet: its ground is only lowered by DATUM (terrain.datum; "auto": its lowest point, so the
              lowest ground, usually the river, is at 0 and the viewer's sea plane stays below everything)
  inland      every inland water body (05_ground.py's water layer, touching pieces merged) whose ground is
  water       nearly level (spread under FLAT_SPREAD: lakes, reservoirs, ponds, rivers on the plain) lies
              flat at its level, the ground within WATER_FLAT of its banks too; beyond, the ground rises to
              its own height by WATER_RAMP and nowhere falls away from the water faster than BANK_SLOPE (the
              dams of 西丽, 铁岗 and 石岩 reservoirs become embankments). Water on a slope (streams in the
              hills) keeps the ground under it
Then the ground becomes a TIN, by greedy Delaunay insertion on the TIN_CELL grid: the node furthest off
in each triangle is added until none is further than TIN_ERROR (TIN_ERROR_FAR beyond the districts,
TIN_ERROR_EDGE where the coast and the water hold the ground level, so lakes stay flat).
Delaunay keeps it a proper height field (a simplifier's edge collapses can fold triangles over each other
in flat areas). From here on the TIN is the ground: every later step reads it through common.Terrain, and
06_tiles.py hands it to the viewer, so buildings, roads, trees and cars all agree on one surface.

Backdrop: beyond the ground area there is only the sea plane, but from the city the hills of Hong Kong
(大帽山 957 m, 青山 583 m), 梧桐山 (944 m) and Dongguan fill the skyline. The DEM's surface (it has no trees
drawn on it) is averaged onto a FAR_CELL grid out to FAR_REACH beyond the ground area (as far as the two DEM
tiles reach), dropped like the ground, and made a TIN of its own (BACK_ERROR, growing with distance) whose
inner edge takes the ground TIN's heights exactly where the ground layers end, so the two meet without a
seam. Sea (the DEM's 0) is left out; each vertex gets a colour from its slope and height (forest on the hills,
towns and fields on the flats) and water where the DEM is dead level.

Writes terrain.npz in the data folder, checks/terrain.png (hillshade) and checks/terrain.md (peaks, [terrain.peaks]).
"""
import time
from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.tri as mtri
import numpy as np
import rasterio
import rasterio.features
import rasterio.warp
from affine import Affine
from pyproj import Transformer
from rasterio.merge import merge
from rasterio.warp import Resampling, reproject
from scipy import ndimage as ndi
from shapely.ops import unary_union

from .. import sources
from ..common import CFG, CHECKS, DATA, TERRAIN, UTM, boundary

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

C = CFG["terrain"]
DEM_SOURCE = sources.module(CFG["sources"]["dem"])
DEM = DEM_SOURCE.tiles()
BACK_SOURCE = sources.module(CFG["sources"]["backdrop"] or CFG["sources"]["dem"])    # the hills beyond
BACK = BACK_SOURCE.tiles("backdrop")
WORK = C["work"]              # metres, the estimation grid
TIN_CELL = C["tin_cell"]      # metres, the TIN's vertices are nodes of this grid (every other WORK node)
BUILDING_PAD = C["building_pad"]   # metres around footprints masked out of the DEM
OPEN = C["open"]              # metres, the opening's window (fallbacks: OPEN_FILL for masked blocks)
OPEN_FILL = tuple(C["open_fill"])
CANOPY = C["canopy"]          # metres off the DEM per OSM class
SMOOTH_OPEN, SMOOTH_TOWN = C["smooth_open"], C["smooth_town"]   # Gaussian sigma (m); town weight from the footprint cover
SMOOTH_BARE = C["smooth_bare"]      # Gaussian sigma (m) for a bare-earth DEM
SEA_DROP, SEA_KNEE = C["sea_drop"], C["sea_knee"]       # metres: ground below SEA_DROP is 0, above it drops by SEA_DROP + KNEE
COAST_FLAT, COAST_RAMP = C["coast_flat"], C["coast_ramp"]   # metres from the sea
FLAT_SPREAD = C["flat_spread"]     # metres (10th to 90th percentile of the ground under a water body)
WATER_FLAT, WATER_RAMP = C["water_flat"], C["water_ramp"]   # metres from the water's edge
BANK_SLOPE = C["bank_slope"]
# a water body's cells: every cell it touches (true: a 10 m grid's narrow streams and canals are held level
# whole), or only those whose centre it covers (false: on a 5 m lidar grid the cell by a quay wall is the
# quay's, and the road along it doesn't drop to the water)
WATER_TOUCHED = C.get("water_all_touched", True)
TIN_ERROR, TIN_ERROR_FAR, TIN_ERROR_EDGE = C["tin_error"], C["tin_error_far"], C["tin_error_edge"]   # metres
# within BANK_REACH m of levelled water the TIN keeps TIN_ERROR_BANK (Paris's quays: the lower quay 2 m over the
# water, then the wall to the upper quay, each a few metres wide); 0: as elsewhere
TIN_ERROR_BANK, BANK_REACH = C.get("tin_error_bank", 0.0), C.get("bank_reach", 40.0)
# steps (the wall from an upper to a lower quay, a road's cutting): every TIN_CELL node whose ground differs from a
# neighbouring node's by at least TIN_STEPS m is a vertex, so the step is a regular one-cell ramp along the grid instead
# of the greedy TIN's long slivers from sparse top and bottom vertices (rows of light spikes along Paris's lower
# quays and La Defense's Boulevard circulaire); 0: off
TIN_STEPS = C.get("tin_steps", 0.0)
# river quays (Paris's Seine): the step from the water to the quay kept inside one TIN cell at the water's edge,
# which 05e_shores covers with a vertical wall and an apron ([shores] quay_walls); off: as before
QUAY_WALLS = C.get("quay_walls", False)
QUAY_MIN, QUAY_DEPTH = C.get("quay_min", 1.0), C.get("quay_depth", 6.0)
# slabs held flat (La Défense's dalle): polygons [[lon, lat], ...], each on its own plane fitted to the ground
DALLES = C.get("dalles", [])
# ground re-filled from its outline (polygons [[lon, lat], ...]): a pit in the lidar (a structure dug into a slope,
# a filled hole) replaced by the surface spanned by the ground round it (linear over a triangulation of the ring)
PATCHES = C.get("patches", [])
# [terrain] patches_file (opt-in, off: ""): the same for every Polygon / MultiPolygon in a GeoJSON file (WGS84; a path
# from the city folder, or absolute), for patches generated by a city script (Hong Kong M3: the 2020 LiDAR's
# excavations under 126 LandsD buildings built since, too many to list inline); its exterior rings join PATCHES
PATCHES_FILE = str(C.get("patches_file", "") or "")
# water bodies held at a given level (scene y, m), whatever the ground under them reads: {name: [lon, lat, level]}, the
# body containing the point (Tokyo: the Sumida and the canals are tidal, the sea's level, but the 5 m DEM over them
# reads 0.5-2.5 m, a median 0.9 m over the bay's 0 at their mouths). Levelled even when their spread is over
# flat_spread. Empty: off, as before
WATER_LEVELS_AT = C.get("water_levels", {})
# construction pits and basements a bare-earth DEM holds (London's lidar: the Tideway shafts at -31 m, Nine Elms'
# at -42.5 m, Battersea's basements): {below, grow, window}. A dry cell whose height (the DEM's own metres, before
# the datum) is under `below` seeds a pit; the pit is every dry cell connected to a seed that lies more than `grow`
# m under the ground's closing over `window` m (the surface with every narrower hole filled); it is re-filled
# from its outline as a patch. Empty: off
PITS = C.get("pits", {})
# the ground DEM's no-data cells filled from the backdrop DEM ({open, smooth, edge, blend} m; see gap_fill); empty: off
GAP_FILL = C.get("gap_fill", {})
# rail and motorway cuttings beyond the drawn roads ({beyond, ways, near, grow, window}): more than `beyond` m outside
# the districts (past [roads] margin, where no road or track is drawn in them) a cutting is only a trench under the
# town layer, which the relief shading drew as smeared soft bands across the overview (Berlin's Ringbahn and A100):
# every dry hollow lying `grow` m under the ground's closing over `window` m within `near` m of one of `ways` (OSM's
# ground-level highway / railway values) is filled to grade from its outline; empty: off
CUTTINGS = C.get("cuttings", {})
# bridge abutments ({reach, ramp, landings} or true; off: {}): a lidar DTM has no bridges, so under a road deck's end
# it reads the water, the foot of a quay wall or the hollow under the first arch, and the road meeting the deck dipped
# metres into that notch before climbing back to its level a few metres on (a step at 140 of Berlin's road deck ends,
# 388 of Paris's, 231 of London's). Where a road deck meets a road at ground level (05b_roads' pins, from its cache),
# the ground there is raised to the road's level (each road's line through its dry ground 8-20 m on, carried back to
# the node; the median of 4 m to `reach` m (12) on a shorter road; the median over the roads), over the deck's end (the grid square round the node, and the deck's width
# up to 5.5 m into the bridge) and along those roads (their width, at most 6 m each side) easing to their own
# ground at `ramp` m (20); only ever raised. 05b_roads then ends the deck on the ground at the node. `landings`:
# footbridges (names) whose ends meet no road fetched (footways on to an avenue) and take the highest dry ground
# within 10 m, the ground raised to it there and on the way to it (the Passerelle Debilly's end on the
# Avenue de New York, 2 m over the lower quay under it)
_DE = C.get("deck_ends", {})
DECK_ENDS = {"on": True} if _DE is True else (_DE if isinstance(_DE, dict) else {})
# [terrain] edge_land (opt-in, off by default): the land layer ends at the ground area's outline, the work grid a cell
# or two beyond it, so those outer cells read as sea and the coast ramp (0 within COAST_FLAT, rising over COAST_RAMP)
# ran round the whole land edge: a 200 m trench to 0 m along the area's edge, with the backdrop's inner edge at the
# land's real height beside it (Singapore M3: rows of 30-47 m pyramids along the edge). True: the cells within
# EDGE_LAND_CELLS of the outline (and beyond it) take the land/sea of the nearest cell further inside
EDGE_LAND = C.get("edge_land", False)
EDGE_LAND_CELLS = 3
FAR_FROM, FAR_OVER = C["far_from"], C["far_over"]   # districts + this is "far": the error grows over FAR_OVER m
FAR_CELL = C["far_cell"]      # backdrop grid (m)
# m added to the backdrop's DEM: a surface model beyond a bare-earth ground (Berlin: Copernicus GLO-30 reads ~4.8 m
# over the DGM1 by median, its buildings and woods) is let down by its bias so the two meet at the seam; 0: off
BACK_SHIFT = float(C.get("back_shift", 0.0))
FAR_REACH = C["far_reach"]    # backdrop reaches this far beyond the ground area (m)
# [terrain] far_reach_sides = [west, south, east, north] (m; opt-in, Tokyo M7; default none: far_reach on every side): the
# backdrop's reach per side, so one far sector (Mount Fuji 100 km west-south-west of Tokyo, the Chichibu and Tanzawa
# ranges) comes in without a 200 x 200 km square of plain and sea round it; the TIN's error still grows over far_reach
FAR_SIDES = C.get("far_reach_sides") or [FAR_REACH] * 4
# [terrain] back_sea = "void" (opt-in, Tokyo M7; default "level"): with a bare-earth backdrop, the sea is only where its
# first file has no data (GSI's tiles are void over the sea; a later file, GLO-30, fills it at 0), not all land at or
# under 0.2 m: the polders and zero-metre lowlands (Katsushika, Edogawa: -1 to -3 m T.P. behind their levees) went to the
# sea's -3 and the sea plane showed through them as blue blob "lakes" across the far plain (Tokyo M3, M6 critic)
BACK_SEA = C.get("back_sea", "level")
# [terrain] curvature = {from, k} (opt-in, Tokyo M7; default none): the earth's curvature on the backdrop as seen from the
# city: past `from` m from the scene's origin a drop D = (r - from)^2 / (2 R / (1 - k)) (R 6,371 km, k the refraction
# coefficient, 0.13), applied as y^2 / (y + D) so the land never goes under the sea plane (a low coast, which in truth
# lies under the horizon at that range, keeps a sliver over it): Mount Fuji 98 km out stands ~3,150 m over the plain
# as the eye sees it from Tokyo Tower, not 3,776 m (24 % too tall without it); the hills at 40 km lose 2-5 %
CURVATURE = C.get("curvature") or {}
BACK_ERROR = tuple(C["back_error"])   # backdrop TIN error at its inner edge and at FAR_REACH (m)
SEA_Y = C["sea_y"]            # backdrop vertices on the sea: below the sea plane, so the coast is where
                              # the surface crosses it (the viewer cuts the backdrop off at -1)
DATUM = C["datum"]            # inland only: metres taken off the DEM ("auto": its lowest point on the ground)
# true: dem_on reads each CRS's run of DEM tiles only over the grid it fills (+ 2 cells), on the run's own pixel
# grid, merged into a temporary tiled GeoTIFF in the data folder and warped from it in chunks (_warp_window), so no
# whole mosaic is held in memory. Hong Kong: the 2 m LiDAR mosaic and the territory's 5 m DTM are one EPSG:2326 run,
# merged whole at 2 m (64 x 48 km, 3 GB a copy, 02_dem peaked at 10.2 GB), on the union's corner, half a pixel off
# the LiDAR's grid. Cells no tile covers are NaN (the next run or the nearest-cell fill takes them) instead of
# merge's 0. false: the whole run merged in memory at its finest resolution first, as before
DEM_WINDOW = bool(C.get("dem_window", False))

# named summits, for checks/terrain.md: lon, lat, surveyed height (m; None: not checked)
PEAKS = {k: (v[0], v[1], v[2] if len(v) > 2 else None) for k, v in C["peaks"].items()}
# the summit table's search radius (m; checks/terrain.md): 1 km took a neighbouring higher hill's top for a low
# summit's (London: Primrose Hill read Hampstead's slope); 30-50 m, as 02_dem's table, finds the summit itself
PEAK_R = float(C.get("peak_radius", 1000.0))
# [terrain] summits = {radius} (opt-in, Singapore M7; empty: off): the named [terrain.peaks] in the ground area that
# the canopy cut and the smoothing brought under their surveyed height (less the sea drop: the scene's plain lies that
# much under the DEM's) lifted back to it: the hill within `radius` m of its top scaled up over its foot (the 5th
# percentile of the ground there), fully within a third of the radius, easing out to none at it (Mount Faber 106 m
# stood at 91, Serapong 90 at 80)
SUMMITS = C.get("summits") or {}
LOG = []
WATER_LEVELS = []     # (polygon, level or None: left on its slope, 10th and 90th percentile), for the checks


def log(msg):
    print(msg, flush=True)
    LOG.append(msg)


# ---------------------------------------------------------------- grids

def scene_grid(origin, bounds, cell):
    """Nodes (x0 + i cell, z0 + j cell) in scene coordinates covering bounds (UTM), and the raster
    transform whose pixel centres are those nodes (row 0 at the north, as z grows southwards)."""
    ax0, ay0, ax1, ay1 = bounds
    x0 = np.floor((ax0 - origin[0]) / cell) * cell
    x1 = np.ceil((ax1 - origin[0]) / cell) * cell
    z0 = np.floor(-(ay1 - origin[1]) / cell) * cell
    z1 = np.ceil(-(ay0 - origin[1]) / cell) * cell
    nx, nz = int(round((x1 - x0) / cell)) + 1, int(round((z1 - z0) / cell)) + 1
    tr = Affine(cell, 0, origin[0] + x0 - cell / 2, 0, -cell, origin[1] - z0 + cell / 2)
    return x0, z0, nx, nz, tr


def dem_on(tr, shape, resampling, paths=None):
    """The DEM's tiles (or those of paths) mosaicked and resampled onto a scene grid; no data is NaN.
    Tiles in several CRSs (sources/geotiff.py: a lidar mosaic, then a national DTM beyond it): each CRS's run of
    tiles mosaicked and warped on its own, an earlier run's data winning; only the tiles over the grid are read."""
    paths = list(DEM if paths is None else paths)
    srcs = [rasterio.open(p) for p in paths]
    shifts = sources.geotiff_shifts()            # [sources.geotiff] entries' vertical shifts (m), {} when none
    shift_of = lambda s: shifts.get(s.name, 0.0) if shifts else 0.0   # noqa: E731
    runs = []                                    # consecutive tiles in one CRS (and one vertical shift)
    for s in srcs:
        if runs and runs[-1][0].crs == s.crs and shift_of(runs[-1][0]) == shift_of(s):
            runs[-1].append(s)
        else:
            runs.append([s])
    out = None
    for run in runs:
        if len(runs) > 1 or DEM_WINDOW:
            # the grid's bounds in the run's CRS (a margin of 2 cells): tiles outside it are not read
            gx0, gy1 = tr * (0, 0)
            gx1, gy0 = tr * (shape[1], shape[0])
            b = rasterio.warp.transform_bounds(UTM, run[0].crs, gx0, gy0, gx1, gy1)
            m = 2 * max(abs(tr.a), abs(tr.e)) * (1 if run[0].crs.is_projected else 1e-5)
            # snapped outwards onto the run's pixel grid, so merge reads its pixels where they are (unsnapped
            # bounds shifted the mosaic by up to half a pixel)
            t0 = run[0].transform
            rx, ry = abs(t0.a), abs(t0.e)
            b = (t0.c + np.floor((b[0] - m - t0.c) / rx) * rx, t0.f + np.floor((b[1] - m - t0.f) / ry) * ry,
                 t0.c + np.ceil((b[2] + m - t0.c) / rx) * rx, t0.f + np.ceil((b[3] + m - t0.f) / ry) * ry)
            run = [s for s in run if s.bounds.left < b[2] and s.bounds.right > b[0]
                   and s.bounds.bottom < b[3] and s.bounds.top > b[1]]
            if not run:
                continue
        nodata = run[0].nodata
        if DEM_WINDOW:
            part = _warp_window(run, b, nodata, tr, shape, resampling)
        else:
            if len(runs) > 1:      # (cells no tile covers: NaN, not 0, so the next run fills them)
                mosaic, mtr = merge(run, bounds=b, nodata=nodata if nodata is not None else np.nan)
            else:
                mosaic, mtr = merge(run)
            src = mosaic[0].astype(np.float32)
            if nodata is not None:
                src[src == nodata] = np.nan
            part = np.zeros(shape, np.float32)
            reproject(src, part, src_transform=mtr, src_crs=run[0].crs, src_nodata=np.nan, dst_transform=tr,
                      dst_crs=UTM, resampling=resampling, dst_nodata=np.nan)
            del src, mosaic
        if shift_of(run[0]):
            part += np.float32(shift_of(run[0]))
        if out is None:
            out = part
        else:
            gap = np.isnan(out)
            out[gap] = part[gap]
    for s in srcs:
        s.close()
    return out if out is not None else np.full(shape, np.nan, np.float32)


def burn(shape, tr, geoms, value=1, dtype="uint8", out=None):
    shapes = ((g, v) for g, v in zip(geoms, value if not np.isscalar(value) else [value] * len(geoms))
              if g is not None and not g.is_empty)
    if out is not None:
        rasterio.features.rasterize(shapes, out=out, transform=tr)
        return out
    return rasterio.features.rasterize(shapes, out_shape=shape, transform=tr, dtype=dtype)


# ---------------------------------------------------------------- bare earth

def opening(f, px):
    """Grey opening with a px x px square; +inf (masked) is ignored by the minimum, -inf stays unknown."""
    e = ndi.minimum_filter(f, size=px)
    e[~np.isfinite(e)] = -np.inf
    return ndi.maximum_filter(e, size=px)


def bare_earth(dsm, tr, origin):
    t0 = time.time()
    shape = dsm.shape
    b = gpd.read_file(DATA / "buildings.gpkg").to_crs(UTM)
    built = burn(shape, tr, list(b.geometry.buffer(BUILDING_PAD, resolution=2))).astype(bool)
    del b
    f = np.where(built, np.inf, dsm).astype(np.float32)
    g = opening(f, int(OPEN / WORK) | 1)
    for w in OPEN_FILL:
        bad = ~np.isfinite(g)
        if not bad.any():
            break
        g[bad] = opening(f, int(w / WORK) | 1)[bad]
    g[~np.isfinite(g)] = 0
    del f
    log(f"buildings: {built.mean():.1%} of the area masked; opened ({time.time() - t0:.0f} s)")

    from . import trees as trees08
    area = gpd.read_file(DATA / "ground.gpkg", layer="area").geometry.iloc[0]
    green = trees08.fetch_green(area)
    green = green[green.cls.isin(list(CANOPY))]
    green = green.assign(a=green.area).sort_values("a", ascending=False)   # smaller areas win
    can = burn(shape, tr, list(green.geometry), [CANOPY[c] for c in green.cls], out=np.zeros(shape, np.float32))
    g -= ndi.gaussian_filter(can, 40 / WORK)
    del can
    # built-up share round each node decides between the two smoothings
    town = np.clip((ndi.uniform_filter(built.astype(np.float32), int(200 / WORK)) - 0.08) / 0.25, 0, 1)
    del built
    g = ndi.gaussian_filter(g, SMOOTH_OPEN / WORK) * (1 - town) + ndi.gaussian_filter(g, SMOOTH_TOWN / WORK) * town
    log(f"canopy and smoothing ({time.time() - t0:.0f} s)")
    return g.astype(np.float32)


def gap_fill(dem, tr, shape):
    """[terrain] gap_fill: the ground DEM's no-data cells (Berlin: the DGM1's 2 km tiles leave the ground area's
    corners bare; bare_smooth's nearest-cell fill drew them as stretched-column streaks) filled from the backdrop
    DEM, its buildings and woods opened out over `open` m and smoothed `smooth` m (a surface model), plus an offset:
    the two DEMs' difference along the gap's edge (smoothed over `edge` m), easing over `blend` m into their median
    difference, so the filled ground meets the edge without a step. Empty: off (the nearest-cell fill)."""
    gap = ~np.isfinite(dem)
    if not GAP_FILL or not gap.any():
        return dem
    t0 = time.time()
    px = int(GAP_FILL.get("open", 150.0) / WORK) | 1
    b = dem_on(tr, shape, Resampling.bilinear, BACK)
    bok = np.isfinite(b)
    if not bok.any():
        return dem
    b = np.where(bok, b, np.nanmedian(b)).astype(np.float32)
    if px > 1:
        b = ndi.maximum_filter(ndi.minimum_filter(b, size=px), size=px)
    b = ndi.gaussian_filter(b, GAP_FILL.get("smooth", 60.0) / WORK).astype(np.float32)
    ok = ~gap & bok
    d = np.where(ok, dem - b, 0).astype(np.float32)
    bias = float(np.median(d[ok][::97]))
    # the difference near the edge, a normalised Gaussian over the known cells
    s = GAP_FILL.get("edge", 150.0) / WORK
    w = ndi.gaussian_filter(ok.astype(np.float32), s)
    de = ndi.gaussian_filter(d, s) / np.maximum(w, 1e-6)
    del d, w
    dist, idx = ndi.distance_transform_edt(gap, return_indices=True)
    de = de[tuple(idx)]
    del idx
    fade = np.clip(1 - dist * WORK / GAP_FILL.get("blend", 600.0), 0, 1)
    fade = fade * fade * (3 - 2 * fade)
    out = dem.copy()
    fill = b + bias + (de - bias) * fade
    out[gap & bok] = fill[gap & bok]
    log(f"gap fill: {gap.mean():.2%} of the work grid from the backdrop DEM (opened {px * WORK:.0f} m), its median "
        f"offset {bias:+.2f} m, the edge's eased in over {GAP_FILL.get('blend', 600.0):.0f} m ({time.time() - t0:.0f} s)")
    return out


def bare_smooth(dem):
    """A bare-earth DEM (lidar DTM, the adapter's BARE) needs none of the above: buildings and trees are
    already out. Holes (no data) are filled from the nearest known ground, then it is only smoothed a
    little (terrain.smooth_bare), so kerb-to-kerb noise and bridge abutments' spikes don't reach the TIN."""
    g = dem.copy()
    bad = ~np.isfinite(g)
    if bad.any():
        idx = ndi.distance_transform_edt(bad, return_distances=False, return_indices=True)
        g = g[tuple(idx)]
    log(f"bare earth ({DEM_SOURCE.__name__.rsplit('.', 1)[-1]}): {bad.mean():.2%} filled, smoothed {SMOOTH_BARE:.0f} m")
    return ndi.gaussian_filter(g, SMOOTH_BARE / WORK).astype(np.float32)


def sea_drop(h):
    """Heights over the sea -> scene heights: 0 below SEA_DROP, then rising with a soft knee of SEA_KNEE
    (continuous in value and slope) to the height less SEA_DROP + SEA_KNEE."""
    x = h - SEA_DROP
    k = SEA_KNEE
    return np.where(x <= 0, 0, np.where(x < 2 * k, x * x / (4 * k), x - k)).astype(np.float32)


def coastal(area, land) -> bool:
    """Whether the ground area meets the sea (city.toml coast; "auto": some of it lies off the land)."""
    if CFG["coast"] != "auto":
        return bool(CFG["coast"])
    return area.difference(unary_union(list(land))).area > 1e-3 * area.area


def coast_ramp(to_sea):
    """0 within COAST_FLAT of the sea, rising smoothly to 1 over COAST_RAMP."""
    r = np.clip((to_sea - COAST_FLAT) / COAST_RAMP, 0, 1)
    return r * r * (3 - 2 * r)


def inland_water(g, tr, water_geoms, pooled=False):
    """Level every nearly level water body and its banks (see the module docstring). Returns the mask of
    everything held level (for the TIN's tighter error) and counts."""
    shape = g.shape
    if pooled:            # 05_ground's pools (split at dams and locks): one body each, already merged
        parts = [p for p in water_geoms if p is not None and not p.is_empty]
    else:
        parts = unary_union(water_geoms)
        parts = getattr(parts, "geoms", [parts])
    parts = sorted(parts, key=lambda p: -p.area)
    levels = []
    n_quay = 0
    held = np.zeros(shape, bool)
    fixed = []
    if WATER_LEVELS_AT:
        import shapely
        to = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
        fixed = [(name, shapely.Point(*to.transform(v[0], v[1])), float(v[2])) for name, v in WATER_LEVELS_AT.items()]
    reach = WATER_RAMP + 60
    n_flat = n_slope = 0
    inv = ~tr
    for p in parts:
        if p.area < 200:
            continue
        x0, y0, x1, y1 = p.bounds
        c0, r0 = inv * (x0 - reach, y1 + reach)
        c1, r1 = inv * (x1 + reach, y0 - reach)
        c0, r0 = max(int(c0), 0), max(int(r0), 0)
        c1, r1 = min(int(np.ceil(c1)), shape[1]), min(int(np.ceil(r1)), shape[0])
        if c1 - c0 < 2 or r1 - r0 < 2:
            continue
        wtr = tr * Affine.translation(c0, r0)
        m = rasterio.features.rasterize([(p, 1)], out_shape=(r1 - r0, c1 - c0), transform=wtr,
                                        dtype="uint8", all_touched=WATER_TOUCHED).astype(bool)
        if not m.any():
            continue
        win = g[r0:r1, c0:c1]
        lo, level, hi = np.percentile(win[m], [10, 50, 90])
        at = next(((n, v) for n, q, v in fixed if p.covers(q)), None)
        if at is not None:
            log(f"water_levels: {at[0]} held at {at[1]:.2f} m (its ground's median {level:.2f}, p10-p90 "
                f"{lo:.2f}-{hi:.2f})")
            level = at[1]
        elif hi - lo > FLAT_SPREAD:
            n_slope += 1
            levels.append((p, None, lo, hi))
            continue
        n_flat += 1
        levels.append((p, float(level), lo, hi))
        d = ndi.distance_transform_edt(~m) * WORK
        ramp = np.clip((d - WATER_FLAT) / (WATER_RAMP - WATER_FLAT), 0, 1)
        up = level + np.maximum(win - level, 0) * ramp * ramp * (3 - 2 * ramp)
        down = np.maximum(win, level - BANK_SLOPE * np.maximum(d - WATER_FLAT, 0))
        g[r0:r1, c0:c1] = np.where(win >= level, up, down)
        held[r0:r1, c0:c1] |= d <= WATER_FLAT
        if QUAY_WALLS:
            n_quay += quay_step(g[r0:r1, c0:c1], m, d, level)
    WATER_LEVELS[:] = levels
    if QUAY_WALLS:
        log(f"quay walls: {n_quay:,} land cells along the water raised to their quay, the water beside them "
            f"{QUAY_DEPTH:.0f} m under its level")
    return held, n_flat, n_slope


def quay_step(win, m, d, level):
    """A levelled body's quays (see QUAY_WALLS), in place on its window: the first ring of land cells (the
    lidar's wall smeared over them, half way up) takes the highest of the next ring inland, where it stands
    QUAY_MIN over the water; the water cells next to such a quay drop QUAY_DEPTH under the level, so the TIN
    crosses the water's surface close to the quay (inside the wall 05e_shores draws). Returns the quay cells."""
    ring1 = (d > 0) & (d <= 1.5 * WORK)
    ring2 = (d > 1.5 * WORK) & (d <= 2.9 * WORK)
    inner = ndi.maximum_filter(np.where(ring2, win, -np.inf), size=3)
    lift = np.where(ring1 & np.isfinite(inner), np.maximum(win, inner), win)
    quay = ring1 & (lift - level >= QUAY_MIN)
    win[quay] = lift[quay]
    wet = m & (ndi.distance_transform_edt(m) * WORK <= 1.5 * WORK) & ndi.binary_dilation(quay, np.ones((3, 3), bool))
    win[wet] = np.minimum(win[wet], level - QUAY_DEPTH)
    return int(quay.sum())


def patch_rings(path) -> list:
    """[terrain] patches_file: the exterior rings ([[lon, lat], ...]) of every Polygon / MultiPolygon in a GeoJSON file
    (a FeatureCollection, a Feature, a GeometryCollection or a bare geometry). A missing file or one without any
    polygon is an error naming the key."""
    import json
    from ..common import CITY
    p = Path(path)
    p = p if p.is_absolute() else CITY / p
    if not p.is_file():
        raise FileNotFoundError(f"[terrain] patches_file = {path!r} ({p}): no such file (GeoJSON, WGS84 polygons)")
    rings = []

    def walk(o):
        t = o.get("type") if isinstance(o, dict) else None
        if t == "FeatureCollection":
            for f in o.get("features") or []:
                walk(f)
        elif t == "Feature":
            walk(o.get("geometry"))
        elif t == "GeometryCollection":
            for q in o.get("geometries") or []:
                walk(q)
        elif t == "Polygon":
            rings.append(o["coordinates"][0])
        elif t == "MultiPolygon":
            rings.extend(poly[0] for poly in o["coordinates"])

    walk(json.loads(p.read_text()))
    if not rings:
        raise ValueError(f"[terrain] patches_file = {path!r} ({p}): no Polygon or MultiPolygon in it")
    return rings


def patches(g, tr):
    """[terrain] patches (and patches_file): each polygon's cells re-filled from the ground just outside it."""
    from_file = patch_rings(PATCHES_FILE) if PATCHES_FILE else []
    if not PATCHES and not from_file:
        return
    from scipy.interpolate import griddata
    from shapely.geometry import Polygon
    to = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    n_file, a_file, up_file = 0, 0.0, []
    for k, ring in enumerate(list(PATCHES) + from_file):
        quiet = k >= len(PATCHES)
        poly = Polygon([to.transform(lo, la) for lo, la in ring])
        m = burn(g.shape, tr, [poly]).astype(bool)
        if m.sum() < 2:
            continue
        edge = ndi.binary_dilation(m, np.ones((3, 3), bool)) & ~m
        re, ce = np.nonzero(edge)
        r, c = np.nonzero(m)
        before = g[r, c].copy()
        g[r, c] = griddata(np.column_stack([ce, re]), g[re, ce], np.column_stack([c, r]), method="linear",
                           fill_value=float(np.median(g[re, ce])))
        if quiet:
            n_file, a_file = n_file + 1, a_file + m.sum() * WORK * WORK
            up_file.append(float(np.abs(g[r, c] - before).max()))
            continue
        log(f"patch: {m.sum() * WORK * WORK:.0f} m² re-filled from its outline (ground moved up to "
            f"{np.abs(g[r, c] - before).max():.1f} m)")
    if from_file:
        log(f"patches_file: {n_file} of {len(from_file)} polygons re-filled from their outlines, {a_file / 1e4:.1f} ha, "
            f"ground moved up to {max(up_file, default=0):.1f} m (median of the maxima {np.median(up_file) if up_file else 0:.1f} m)")


def fill_pits(g, tr, wet):
    """[terrain] pits (see PITS), in place on g (the DEM's metres) away from water (wet). Returns the pit mask."""
    if not PITS:
        return None
    from scipy.interpolate import griddata
    below, grow = float(PITS.get("below", 0.0)), float(PITS.get("grow", 2.0))
    px = int(float(PITS.get("window", 150.0)) / WORK) | 1
    ref = ndi.grey_closing(g, size=(px, px))
    seed = (g < below) & ~wet
    lab, n = ndi.label(((ref - g > grow) | seed) & ~wet)
    keep = np.unique(lab[seed])
    keep = keep[keep > 0]
    pit = np.isin(lab, keep)
    lab, n = ndi.label(pit)
    moved, area, rows, capped = [], 0, [], []
    # [terrain] pits.keep_ways: highway / railway values (OSM's ground-level ways, 05b_roads' cache) whose cuttings and
    # troughs are real: a pit holding at least keep_len m of one is left as the DEM has it (Berlin's A100 trough)
    kept = []
    kw = set(PITS.get("keep_ways", []))
    way_mask = None
    if kw:
        import json
        from ..common import RAW
        cache = RAW / "osm_roads.json"
        if cache.exists():
            from shapely.geometry import LineString
            to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
            lines = []
            for el in json.loads(cache.read_text())["elements"]:
                t_ = el.get("tags", {})
                if el.get("type") != "way" or len(el.get("geometry", [])) < 2:
                    continue
                if t_.get("highway") not in kw and t_.get("railway") not in kw:
                    continue
                if t_.get("tunnel", "no") != "no" or t_.get("bridge", "no") != "no":
                    continue
                x, y = to_utm.transform([q["lon"] for q in el["geometry"]], [q["lat"] for q in el["geometry"]])
                lines.append(LineString(np.column_stack([x, y])))
            way_mask = burn(g.shape, tr, [ln.buffer(WORK / 2) for ln in lines]).astype(bool) if lines else None
        min_cells = float(PITS.get("keep_len", 50.0)) / WORK
    cap = PITS.get("max_raise")
    cap = None if cap is None else float(cap)
    for k, sl in enumerate(ndi.find_objects(lab), 1):
        sl = tuple(slice(max(s.start - 2, 0), s.stop + 2) for s in sl)
        m = lab[sl] == k
        win = g[sl]
        if way_mask is not None and (way_mask[sl] & m).sum() >= min_cells:
            lab[sl][m] = 0
            kept.append((int(m.sum()), sl, m))
            continue
        edge = ndi.binary_dilation(m, np.ones((3, 3), bool)) & ~m
        re, ce = np.nonzero(edge)
        r, c = np.nonzero(m)
        before = win[r, c].copy()
        if len(re) >= 3:
            win[r, c] = griddata(np.column_stack([ce, re]), win[re, ce], np.column_stack([c, r]), method="linear",
                                 fill_value=float(np.median(win[re, ce])))
        else:
            win[r, c] = float(np.median(win[re, ce])) if len(re) else win[r, c]
        up = win[r, c] - before
        if cap is not None and up.max() > cap:
            # [terrain] pits.max_raise: a hole deeper than this under its outline is not a dug pit (a railway
            # or road cutting, a dock basin the water layer missed): left as the DEM has it
            win[r, c] = before
            lab[sl][m] = 0
            capped.append((float(up.max()), int(m.sum()), sl, m))
            continue
        moved.append(float(up.max()))
        area += int(m.sum())
        rows.append((int(m.sum()), float(up.max()), float(up.mean()), float(np.median(win[re, ce])) if len(re) else 0.0,
                     sl[0].start + r.mean(), sl[1].start + c.mean()))
    log(f"pits: {len(moved)} dry pits with a cell under {below:.1f} m re-filled from their outlines, "
        f"{area * WORK * WORK / 1e4:.1f} ha, ground raised up to {max(moved, default=0):.1f} m"
        + (f"; {len(capped)} deeper than {cap:.0f} m under their outline left as they are" if cap is not None else ""))
    # the five largest, by area (lon, lat of their centre): what each is decides whether filling it was right
    to_ll = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    for a, top, mean, rim, rr, cc in sorted(rows, reverse=True)[:5]:
        lon, lat = to_ll.transform(*(tr * (cc + 0.5, rr + 0.5)))
        log(f"  pit {a * WORK * WORK / 1e4:.2f} ha at {lat:.5f}, {lon:.5f}: raised up to {top:.1f} m (mean "
            f"{mean:.1f}) to its outline's {rim:.1f} m")
    if kw:
        log(f"pits: {len(kept)} holding a cutting or trough of {', '.join(sorted(kw))} left as they are")
        for a, sl, m in sorted(kept, key=lambda t: -t[0])[:5]:
            r, c = np.nonzero(m)
            lon, lat = to_ll.transform(*(tr * (sl[1].start + c.mean() + 0.5, sl[0].start + r.mean() + 0.5)))
            log(f"  left: {a * WORK * WORK / 1e4:.2f} ha at {lat:.5f}, {lon:.5f} (a cutting)")
    for top, a, sl, m in sorted(capped, key=lambda t: -t[1])[:5]:
        r, c = np.nonzero(m)
        lon, lat = to_ll.transform(*(tr * (sl[1].start + c.mean() + 0.5, sl[0].start + r.mean() + 0.5)))
        log(f"  left: {a * WORK * WORK / 1e4:.2f} ha at {lat:.5f}, {lon:.5f}, {top:.1f} m under its outline")
    return lab > 0


def osm_ways(kinds, shape, tr, half):
    """OSM's ground-level ways of these highway / railway values (05b_roads' cache), burned buffered by half m."""
    import json
    from shapely.geometry import LineString
    from ..common import RAW
    cache = RAW / "osm_roads.json"
    if not cache.exists():
        return None
    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    lines = []
    for el in json.loads(cache.read_text())["elements"]:
        t_ = el.get("tags", {})
        if el.get("type") != "way" or len(el.get("geometry", [])) < 2:
            continue
        if t_.get("highway") not in kinds and t_.get("railway") not in kinds:
            continue
        if t_.get("tunnel", "no") != "no" or t_.get("bridge", "no") != "no":
            continue
        x, y = to_utm.transform([q["lon"] for q in el["geometry"]], [q["lat"] for q in el["geometry"]])
        lines.append(LineString(np.column_stack([x, y])))
    return burn(shape, tr, [ln.buffer(half) for ln in lines]).astype(bool) if lines else None


def fill_cuttings(g, tr, wet):
    """[terrain] cuttings (see CUTTINGS), in place on g, away from water (wet)."""
    if not CUTTINGS:
        return
    from scipy.interpolate import griddata
    t0 = time.time()
    kinds = set(CUTTINGS.get("ways", ["motorway", "motorway_link", "trunk", "rail", "light_rail", "subway"]))
    near = osm_ways(kinds, g.shape, tr, float(CUTTINGS.get("near", 30.0)))
    if near is None:
        log("cuttings: no OSM ways cached (05b_roads), none filled")
        return
    inside = burn(g.shape, tr, [boundary().geometry.iloc[0]]).astype(bool)
    far = ndi.distance_transform_edt(~inside) * WORK > float(CUTTINGS.get("beyond", 1000.0))
    del inside
    px = int(float(CUTTINGS.get("window", 150.0)) / WORK) | 1
    ref = ndi.grey_closing(g, size=(px, px))
    low = (ref - g > float(CUTTINGS.get("grow", 2.0))) & ~wet
    del ref
    # the hollows touching a way's corridor beyond the reach; each grown to its whole low region there
    lab, n = ndi.label(low & far)
    keep = np.unique(lab[near & low & far])
    keep = keep[keep > 0]
    lab[~np.isin(lab, keep)] = 0
    area, top = 0, 0.0
    for k, sl in enumerate(ndi.find_objects(lab), 1):
        if sl is None:
            continue
        sl = tuple(slice(max(s_.start - 2, 0), s_.stop + 2) for s_ in sl)
        m = lab[sl] == k
        if not m.any():
            continue
        win = g[sl]
        edge = ndi.binary_dilation(m, np.ones((3, 3), bool)) & ~m
        re, ce = np.nonzero(edge)
        r, c = np.nonzero(m)
        if len(re) < 3:
            continue
        before = win[r, c].copy()
        win[r, c] = griddata(np.column_stack([ce, re]), win[re, ce], np.column_stack([c, r]), method="linear",
                             fill_value=float(np.median(win[re, ce])))
        win[r, c] = np.maximum(win[r, c], before)
        area += len(r)
        top = max(top, float((win[r, c] - before).max()))
    log(f"cuttings: {len(keep)} hollows along {', '.join(sorted(kinds))} beyond "
        f"{float(CUTTINGS.get('beyond', 1000.0)):.0f} m of the districts filled to grade, "
        f"{area * WORK * WORK / 1e4:.1f} ha, up to {top:.1f} m ({time.time() - t0:.0f} s)")


def dalles(g, tr, held):
    """[terrain] dalles: each polygon on the robust plane through the ground under it (fitted, points over a
    metre off dropped, fitted again), held to the edge tolerance in the TIN."""
    if not DALLES:
        return
    from shapely.geometry import Polygon
    to = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    for ring in DALLES:
        poly = Polygon([to.transform(lo, la) for lo, la in ring])
        m = burn(g.shape, tr, [poly]).astype(bool)
        if m.sum() < 10:
            continue
        r, c = np.nonzero(m)
        A = np.column_stack([c, r, np.ones(len(r))]).astype(np.float64)
        y = g[r, c].astype(np.float64)
        ok = np.ones(len(y), bool)
        for _ in range(4):
            coef = np.linalg.lstsq(A[ok], y[ok], rcond=None)[0]
            res = y - A @ coef
            ok = np.abs(res - np.median(res[ok])) <= 1.0
        g[r, c] = A @ coef
        held |= m
        log(f"dalle: {m.sum() * WORK * WORK / 1e4:.1f} ha on a plane at {np.median(A @ coef):.1f} m "
            f"(slope {np.hypot(coef[0], coef[1]) / WORK:.1%}); {(~ok).mean():.0%} of its ground was over a metre off")


def deck_ends(g, tr, water_geoms):
    """[terrain] deck_ends (see DECK_ENDS), in place on g (scene metres, after the water is levelled). Returns the
    mask of the cells raised (kept as TIN vertices with their neighbours), or None."""
    if not DECK_ENDS:
        return None
    import heapq
    from collections import defaultdict
    from . import roads
    got = roads.cached_ways()
    if got is None:
        log("deck ends: no roads cache (raw/osm_roads.json) yet: run 05b_roads, then 05a_terrain again")
        return None
    ways, xy = got
    reach = float(DECK_ENDS.get("reach", 12.0))
    ramp = float(DECK_ENDS.get("ramp", 20.0))
    landings = set(DECK_ENDS.get("landings", []))
    HIGH_LEVEL = DECK_ENDS.get("level") == "high"
    nz, nx = g.shape
    inv = ~tr
    wet = burn(g.shape, tr, list(water_geoms)).astype(bool)

    def cell(p):
        c, r = inv * (float(p[0]), float(p[1]))
        return int(np.floor(r)), int(np.floor(c))

    def centre(r, c):
        return np.array(tr * (c + 0.5, r + 0.5))

    flat = defaultdict(list)          # the ground-level road network: node -> [(node, length, half width)]
    for w in ways:
        if not w["elevated"] and not w["tunnel"] and w["kind"] not in (None, "rail"):
            hw = float(np.clip(roads.width(w["tags"], w["kind"]) / 2, 2.5, 6.0))
            for a, b in zip(w["nodes"][:-1], w["nodes"][1:]):
                L = float(np.hypot(*np.subtract(xy[a], xy[b])))
                flat[a].append((b, L, hw))
                flat[b].append((a, L, hw))
    into = defaultdict(list)          # deck node -> [(unit vector into the bridge, half width)]
    for w in ways:
        if w["elevated"] and w["kind"] not in (None, "rail"):
            hw = roads.width(w["tags"], w["kind"]) / 2
            ns = w["nodes"]
            for k, k2 in ((0, 1), (len(ns) - 1, len(ns) - 2)):
                d = np.subtract(xy[ns[k2]], xy[ns[k]])
                if np.hypot(*d) > 0.1:
                    into[ns[k]].append((d / np.hypot(*d), hw))
    rows, cols, tgt = [], [], []

    def put(r, c, t, any_=False):
        # not in the water, but for the grid square round the node (the TIN there must hold the deck's level, or the
        # deck's end sank with it towards the river: Lohmühlenbrücke to -2.9 m): raised water cells beside a quay
        # (6 m under the pool with quay_walls) stood as earth wedges in the river under and beside the deck's end
        # (Admiralbrücke, Roßstraßenbrücke)
        if 0 <= r < nz and 0 <= c < nx and (any_ or not wet[r, c]):
            rows.append(r); cols.append(c); tgt.append(t)

    def abutment(p, level, node):
        """The grid square round p (even in the water) and the deck's end (its width, up to 5.5 m into the bridge; dry
        cells) at `level`."""
        r0, c0 = cell(p)
        cf, rf = inv * (float(p[0]), float(p[1]))
        dr, dc = (0 if rf - r0 >= 0.5 else -1), (0 if cf - c0 >= 0.5 else -1)
        for r in (r0 + dr, r0 + dr + 1):
            for c in (c0 + dc, c0 + dc + 1):
                put(r, c, level, True)
        st = int(round(TIN_CELL / WORK))
        if HIGH_LEVEL and st > 1:
            # (level "high": with a TIN coarser than the grid (Tokyo: 20 m over 10 m) the square round the node is the
            # TIN's: its vertices are every st-th cell, and the 10 m square's cells were not among them, so the node
            # read the quay wall's -6 m foot 20 m off: Kachidoki's west deck ends at -1.4 and 0.4 m)
            rs, cs = (r0 // st) * st, (c0 // st) * st
            for r in range(rs, rs + st + 1):
                for c in range(cs, cs + st + 1):
                    put(r, c, level, True)
        for u, hw in into.get(node, []):
            k = int(np.ceil(max(hw, 7.5) / WORK)) + 1
            for r in range(r0 - k, r0 + k + 1):
                for c in range(c0 - k, c0 + k + 1):
                    d = centre(r, c) - p
                    a, x = float(d @ u), float(abs(d[0] * u[1] - d[1] * u[0]))
                    if -7.5 <= a <= 5.5 and x <= hw:
                        put(r, c, level)

    pins = roads.road_pins(ways)
    n_pin = n_free = 0
    done = []                         # the pins raised to their road (05b_roads ends their decks on the ground there)
    for node in pins:
        p = np.asarray(xy[node], float)
        r, c = cell(p)
        if not (0 <= r < nz and 0 <= c < nx):
            continue
        # the ground roads within `ramp` m of the node, sampled every 2 m: (point, distance, half width)
        # (branch: the road leaving the node it lies along)
        best, heap, samp = {node: 0.0}, [(0.0, node, -1)], []
        while heap:
            d, a, br = heapq.heappop(heap)
            if d > best.get(a, np.inf):
                continue
            for k_, (b, L, hw) in enumerate(flat[a]):
                bb = k_ if br < 0 else br
                pa, pb = np.asarray(xy[a], float), np.asarray(xy[b], float)
                for f in np.arange(2.0, min(L, ramp - d) + 1e-9, 2.0):
                    samp.append((pa + (pb - pa) * f / max(L, 1e-9), d + f, hw, bb))
                if d + L < ramp and d + L < best.get(b, np.inf):
                    best[b] = d + L
                    heapq.heappush(heap, (d + L, b, bb))
        if not samp:
            continue
        P = np.array([s[0] for s in samp])
        S = np.array([s[1] for s in samp])
        H = np.array([s[2] for s in samp])
        B = np.array([s[3] for s in samp])
        rc = np.array([cell(q) for q in P])
        ok = (rc[:, 0] >= 0) & (rc[:, 0] < nz) & (rc[:, 1] >= 0) & (rc[:, 1] < nx)
        P, S, H, B, rc = P[ok], S[ok], H[ok], B[ok], rc[ok]
        if not len(P):
            continue
        G = g[rc[:, 0], rc[:, 1]]
        dry = ~wet[rc[:, 0], rc[:, 1]]
        # each road's level at the node: its line through its dry ground 8 m to `ramp` m on (past the notch, its own
        # grade, at most 15 %) carried back to the node and kept within its ground 4 m to `ramp` m on; the median of
        # 4 m to `reach` m where it is too short for that. A road climbing away from the bridge no longer lifts the
        # deck's end to its level 8 m on (the median of all roads put such ends up to 3 m over their own road)
        lines = {}
        for b_ in np.unique(B):
            on = dry & (B == b_)
            fit = on & (S >= 8.0)
            near = on & (S >= 4.0) & (S <= reach)
            if fit.sum() >= 3 and np.ptp(S[fit]) >= 4.0:
                k, c0 = np.polyfit(S[fit], G[fit], 1)
                k = float(np.clip(k, -0.15, 0.15))
                c0 = float(np.median(G[fit] - k * S[fit]))
                span = on & (S >= 4.0)
                lines[b_] = (float(np.clip(c0, G[span].min(), G[span].max())), k)
            elif near.sum() >= 2:
                lines[b_] = (float(np.median(G[near])), 0.0)
        if not lines:
            continue
        level = float(np.median([v[0] for v in lines.values()]))
        if HIGH_LEVEL:
            # (level = "high", opt-in, Tokyo tk2: the Sumida's bridges end at the quay's edge, where the 5 m DEM's notch
            # under the quay wall drops 3-5 m within the road's first 10 m; the fitted line, kept within that ground,
            # ended Kachidoki's west deck at -1.4 and 0.5 m under its 2.8 m street) the highest dry ground within
            # `reach` m along the roads, as 05b_roads' own pins take it
            hi = dry & (S >= 2.0) & (S <= reach)
            if hi.any():
                level = max(level, float(G[hi].max()))
        n_pin += 1
        done.append(int(node))
        abutment(p, level, node)
        # along each road: from the deck's level to its own line at `ramp` m (a dip filled, never cut)
        for q, s, hw, b_ in zip(P, S, H, B):
            c0, grade = lines.get(b_, (level, 0.0))
            t = level + (c0 + grade * ramp - level) * min(s / ramp, 1.0)
            qr, qc = cell(q)
            k = int(np.ceil(hw / WORK))
            for r in range(qr - k, qr + k + 1):
                for c in range(qc - k, qc + k + 1):
                    if np.hypot(*(centre(r, c) - q)) <= hw:
                        put(r, c, t)
    if landings:
        uses = defaultdict(int)
        for w in ways:
            for n in set(w["nodes"]):
                uses[n] += 1
        for w in ways:
            if not (w["elevated"] and w["tags"].get("footbridge") == "yes" and w["tags"].get("name") in landings):
                continue
            for node in (w["nodes"][0], w["nodes"][-1]):
                if uses[node] != 1:
                    continue
                p = np.asarray(xy[node], float)
                r0, c0 = cell(p)
                k = int(np.ceil(10.0 / WORK))
                best = None
                for r in range(max(r0 - k, 0), min(r0 + k + 1, nz)):
                    for c in range(max(c0 - k, 0), min(c0 + k + 1, nx)):
                        q = centre(r, c)
                        if np.hypot(*(q - p)) <= 10.0 and not wet[r, c] and (best is None or g[r, c] > best[0]):
                            best = (float(g[r, c]), q)
                if best is None:
                    continue
                n_free += 1
                level, q = best
                abutment(p, level, node)
                for f in np.linspace(0, 1, max(int(np.hypot(*(q - p)) / 2), 1) + 1):
                    qq = p + (q - p) * f
                    qr, qc = cell(qq)
                    for r in range(qr - 1, qr + 2):
                        for c in range(qc - 1, qc + 2):
                            if np.hypot(*(centre(r, c) - qq)) <= 2.5:
                                put(r, c, level)
    import json
    from ..common import DATA
    (DATA / "deck_ends.json").write_text(json.dumps({"pins": sorted(done)}))
    if not rows:
        return None
    rows, cols, tgt = np.array(rows), np.array(cols), np.array(tgt, np.float32)
    before = g[rows, cols].copy()
    np.maximum.at(g, (rows, cols), tgt)
    up = g[rows, cols] - before
    raised = np.zeros(g.shape, bool)
    raised[rows[up > 0.05], cols[up > 0.05]] = True
    lift = up[up > 0.05]
    # a corner raised in the water: the water cells round it sink `sink` m (24) more, so the TIN's facet from it falls
    # under the water's surface within a fraction of a metre (a vertical abutment face) instead of standing ~2 m out
    # as an earth wedge in the river under the deck's end (Admiralbrücke, Lohmühlenbrücke); the water is opaque
    # (only water cells two cells or more inside the water: one by the bank showed as a 30 m pit in the grass beside the
    # Mehringbrücke, and with water only all round (3x3) the facets to the next ring still opened dark holes by the
    # Pont d'Arcole's left-bank end, where the drawn water stops short of the cell centres)
    inner = ndi.binary_erosion(wet, np.ones((5, 5), bool), border_value=1)
    ring = ndi.binary_dilation(raised & wet, np.ones((3, 3), bool)) & inner & ~raised
    g[ring] -= float(DECK_ENDS.get("sink", 24.0))
    log(f"deck ends: {n_pin} road deck ends and {n_free} footbridge landings; {int(raised.sum()):,} cells raised "
        f"(median {np.median(lift) if len(lift) else 0:.1f} m, 90th percentile "
        f"{np.percentile(lift, 90) if len(lift) else 0:.1f}, max {lift.max() if len(lift) else 0:.1f}), "
        f"{int((raised & wet).sum()):,} of them in the water; {int(ring.sum()):,} water cells round those sunk")
    return raised | ring


# ---------------------------------------------------------------- TIN

def greedy_tin(P, Y, tol, init, extra=None, max_rounds=40, label="TIN"):
    """Greedy Delaunay insertion over a grid: start from the nodes in `init` (and the points in `extra`,
    always kept), then add, in every triangle, the node furthest off relative to its tolerance, until every
    node is within it. P: (nx, nz) grid shape; Y, tol: (nz, nx) heights and tolerances (inf: never needed);
    extra: (i, j, y) arrays of fixed points in grid units, off the nodes. Returns (points (i, j) in grid
    units, heights, triangles into them)."""
    t0 = time.time()
    nx, nz = P
    sel = init.copy()
    ex = extra if extra is not None else (np.zeros(0), np.zeros(0), np.zeros(0))
    for rnd in range(max_rounds):
        nodes = np.flatnonzero(sel)
        pi = np.concatenate([nodes % nx, ex[0]]).astype(np.float64)
        pj = np.concatenate([nodes // nx, ex[1]]).astype(np.float64)
        py = np.concatenate([Y.ravel()[nodes], ex[2]]).astype(np.float64)
        tri = mtri.Triangulation(pi, pj).triangles
        worst, pick = tin_worst(pi[tri], pj[tri], py[tri], Y, tol)
        over = int((worst > 1).sum())
        log(f"  {label} round {rnd}: {len(pi):,} vertices, {len(tri):,} triangles, {over:,} of them off "
            f"({time.time() - t0:.0f} s)")
        if not over or (rnd >= 12 and over < 50):          # the last few only shuffle each other
            break
        sel.ravel()[pick[worst > 1]] = True
    return np.stack([pi, pj], 1), py, tri


def tin_worst(ti, tj, ty, Y, tol, budget=1 << 22):
    """For triangles with corners (ti, tj) in grid units and heights ty (T x 3 each), the worst ratio of a
    grid node's distance from the triangle's plane to its tolerance, and that node (flat index), over the
    nodes inside each triangle (edges included): the triangles are rasterised onto the grid in chunks."""
    nz, nx = Y.shape
    Yf, Tf = Y.ravel(), tol.ravel()
    i0 = np.clip(np.ceil(ti.min(1) - 1e-9), 0, nx - 1).astype(np.int64)
    i1 = np.clip(np.floor(ti.max(1) + 1e-9), 0, nx - 1).astype(np.int64)
    j0 = np.clip(np.ceil(tj.min(1) - 1e-9), 0, nz - 1).astype(np.int64)
    j1 = np.clip(np.floor(tj.max(1) + 1e-9), 0, nz - 1).astype(np.int64)
    w, h = np.maximum(i1 - i0 + 1, 0), np.maximum(j1 - j0 + 1, 0)
    cnt = w * h
    area = (ti[:, 1] - ti[:, 0]) * (tj[:, 2] - tj[:, 0]) - (ti[:, 2] - ti[:, 0]) * (tj[:, 1] - tj[:, 0])
    worst = np.zeros(len(ti))
    pick = np.zeros(len(ti), np.int64)
    ends = np.cumsum(cnt)
    start = 0
    while start < len(ti):
        stop = int(np.searchsorted(ends, (ends[start - 1] if start else 0) + budget, "right"))
        stop = max(stop, start + 1)
        c = cnt[start:stop]
        t = np.repeat(np.arange(start, stop), c)
        k = np.arange(c.sum()) - np.repeat(np.cumsum(c) - c, c)
        ni, nj = i0[t] + k % w[t], j0[t] + k // w[t]
        s = np.sign(area[t])
        # edge functions (twice the sub-triangle areas), positive inside for either winding
        e = []
        for a_, b_ in ((1, 2), (2, 0), (0, 1)):
            e.append(s * ((ti[t, b_] - ti[t, a_]) * (nj - tj[t, a_]) - (tj[t, b_] - tj[t, a_]) * (ni - ti[t, a_])))
        tolr = 1e-9 * np.abs(area[t])
        inside = (e[0] >= -tolr) & (e[1] >= -tolr) & (e[2] >= -tolr) & (area[t] != 0)
        t, ni, nj = t[inside], ni[inside], nj[inside]
        a2 = np.abs(area[t])
        y = (e[0][inside] * ty[t, 0] + e[1][inside] * ty[t, 1] + e[2][inside] * ty[t, 2]) / a2
        node = nj * nx + ni
        r = np.abs(y - Yf[node]) / Tf[node]
        order = np.lexsort((-r, t))
        first = order[np.r_[True, np.diff(t[order]) != 0]] if len(order) else order
        worst[t[first]] = r[first]
        pick[t[first]] = node[first]
        start = stop
    return worst, pick


def ground_tin(T, origin, x0, z0, held_edge, bank=None, keep=None):
    """The ground TIN over the TIN_CELL subgrid of T. Returns vertex grid indices (i, j), heights and
    triangles (counter-clockwise seen from above, scene x-z)."""
    s = int(round(TIN_CELL / WORK))
    G = T[::s, ::s]
    nz, nx = G.shape
    # tolerance per node: TIN_ERROR in the districts, growing to TIN_ERROR_FAR, TIN_ERROR_EDGE by the water
    tr = Affine(TIN_CELL, 0, origin[0] + x0 - TIN_CELL / 2, 0, -TIN_CELL, origin[1] - z0 + TIN_CELL / 2)
    near = burn(G.shape, tr, [boundary().geometry.iloc[0].buffer(FAR_FROM)]).astype(bool)
    far = np.clip(ndi.distance_transform_edt(~near) * TIN_CELL / FAR_OVER, 0, 1)
    tol = (TIN_ERROR + (TIN_ERROR_FAR - TIN_ERROR) * far).astype(np.float32)
    if bank is not None and TIN_ERROR_BANK:
        b = bank[::s, ::s]
        tol[b] = np.minimum(tol[b], TIN_ERROR_BANK)
    tol[held_edge[::s, ::s]] = TIN_ERROR_EDGE
    jj, ii = np.mgrid[0:nz, 0:nx]
    edge = (ii == 0) | (ii == nx - 1) | (jj == 0) | (jj == nz - 1)
    init = (edge & ((ii % 25 == 0) | (jj % 25 == 0))) | ((ii % 50 == 0) & (jj % 50 == 0))
    init[[0, 0, -1, -1], [0, -1, 0, -1]] = True
    if keep is not None:
        # [terrain] deck_ends: the raised cells and the ring round them are vertices (the abutment held exactly, its
        # edge a one-cell ramp)
        k = ndi.binary_dilation(keep, np.ones((3, 3), bool)) if s == 1 else ndi.maximum_filter(keep, size=2 * s + 1)
        init |= k[::s, ::s]
        log(f"  deck ends: {int(k[::s, ::s].sum()):,} nodes kept")
    if TIN_STEPS:
        # a drop to a 4-neighbour of TIN_STEPS m or more (a hillside's slope stays under it: 3 m over 5 m is 60 %)
        drop = np.zeros_like(G)
        for ax in (0, 1):
            dd = np.abs(np.diff(G, axis=ax))
            lo, hi = [slice(None)] * 2, [slice(None)] * 2
            lo[ax], hi[ax] = slice(None, -1), slice(1, None)
            drop[tuple(lo)] = np.maximum(drop[tuple(lo)], dd)
            drop[tuple(hi)] = np.maximum(drop[tuple(hi)], dd)
        # in the districts, not the far ground; not the quay walls' own step down to the water (05e_shores' wall)
        wet = ndi.binary_dilation(held_edge[::s, ::s], np.ones((5, 5), bool))
        steps = (drop >= TIN_STEPS) & (tol <= TIN_ERROR) & ~wet
        init |= steps
        log(f"  steps: {int(steps.sum()):,} nodes where the ground drops {TIN_STEPS:.1f} m to a neighbour kept")
    pts, y, tri = greedy_tin((nx, nz), G, tol, init, label="ground TIN")
    # counter-clockwise seen from above is clockwise in (x, z)
    a, b, c = (pts[tri[:, k]] for k in range(3))
    cross = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
    tri = tri[cross != 0]
    cross = cross[cross != 0]
    tri[cross > 0] = tri[cross > 0][:, [0, 2, 1]]
    return np.round(pts).astype(np.uint16), y.astype(np.float32), tri.astype(np.int32)


# ---------------------------------------------------------------- backdrop

def _warp_window(run, b, nodata, tr, shape, resampling):
    """[terrain] dem_window: a run of tiles merged over bounds b (its own pixel grid) into a temporary tiled
    GeoTIFF in the data folder, chunk by chunk, and warped from there onto the grid by GDAL in chunks too, so
    neither the mosaic nor a float copy of it is ever held whole (Hong Kong: 580 km² at 2 m)."""
    import tempfile
    nd = nodata if nodata is not None else np.nan
    part = np.full(shape, np.nan, np.float32)
    with tempfile.TemporaryDirectory(dir=DATA, prefix=".dem_window_") as d:
        f = Path(d) / "run.tif"
        merge(run, bounds=b, nodata=nd, dtype="float32", dst_path=f,
              dst_kwds={"tiled": True, "blockxsize": 512, "blockysize": 512, "BIGTIFF": "IF_SAFER"})
        with rasterio.open(f) as m:
            reproject(rasterio.band(m, 1), part, src_nodata=nd, dst_transform=tr, dst_crs=UTM,
                      resampling=resampling, dst_nodata=np.nan, warp_mem_limit=256)
    return part


def backdrop(origin, area_bounds, ground, datum=None):
    """The coarse TIN of the land beyond the ground area (see the module docstring)."""
    t0 = time.time()
    ax0, ay0, ax1, ay1 = area_bounds
    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    # as far as the DEM tiles reach (Shenzhen: 22-23 N, 113-115 E)
    w, s, e, n = BACK_SOURCE.extent("backdrop")
    lim = np.array([to_utm.transform(lo, la) for lo, la in ((w, s), (e, s), (w, n), (e, n))])
    rw, rs, re_, rn = FAR_SIDES
    bx0, by0 = max(ax0 - rw, lim[:, 0].min() + 3000), max(ay0 - rs, lim[:2, 1].max() + 300)
    bx1, by1 = min(ax1 + re_, lim[:, 0].max() - 3000), min(ay1 + rn, lim[2:, 1].min() - 300)
    x0, z0, nx, nz, tr = scene_grid(origin, (bx0, by0, bx1, by1), FAR_CELL)
    dsm = np.nan_to_num(dem_on(tr, (nz, nx), Resampling.average, BACK))
    if BACK_SHIFT:
        dsm = np.where(np.abs(dsm) > 0.01, dsm + BACK_SHIFT, dsm)
    zero = np.nan_to_num(dem_on(tr, (nz, nx), Resampling.nearest, BACK))
    # sea: the DEM is exactly 0 over it; a lake is dead level at its own height
    spread = np.nan_to_num(dem_on(tr, (nz, nx), Resampling.max, BACK) - dem_on(tr, (nz, nx), Resampling.min, BACK),
                           nan=1)
    bare = getattr(BACK_SOURCE, "BARE", False)
    void = np.isnan(dem_on(tr, (nz, nx), Resampling.nearest, BACK[:1])) if bare and BACK_SEA == "void" else None
    sea = back_sea_mask(dsm, zero, bare, void)
    if void is not None:
        log(f"backdrop: sea where the bare DEM is void, {int((~void & (dsm < 0.2)).sum()):,} cells of low land kept")
    if datum is not None:                 # inland: no sea, the land lowered like the ground
        sea[:] = False
    lake = ~sea & (spread < 0.05)
    Y = np.where(sea, SEA_Y, sea_drop(dsm) if datum is None else np.maximum(dsm - datum, 0)).astype(np.float32)
    jj, ii = np.mgrid[0:nz, 0:nx]
    X, Z = x0 + ii * FAR_CELL, z0 + jj * FAR_CELL
    H = Y.copy()                                        # the heights before the curvature (back_h: the snow line)
    if CURVATURE:
        Y = np.where(Y > 0, curve(Y, X, Z), Y).astype(np.float32)
    hx0, hx1 = ax0 - origin[0], ax1 - origin[0]
    hz0, hz1 = -(ay1 - origin[1]), -(ay0 - origin[1])
    inside = (X > hx0 - 1) & (X < hx1 + 1) & (Z > hz0 - 1) & (Z < hz1 + 1)
    # the error allowed grows with the distance beyond the ground area; none needed over it
    dist = np.hypot(np.maximum(np.maximum(hx0 - X, X - hx1), 0), np.maximum(np.maximum(hz0 - Z, Z - hz1), 0))
    tol = (BACK_ERROR[0] + (BACK_ERROR[1] - BACK_ERROR[0]) * np.clip(dist / FAR_REACH, 0, 1)).astype(np.float32)
    # the coast: where sea and land meet the surface steps from SEA_Y to the land, and a coarse TIN draws it
    # as long straight chords across bays; nodes along it are held to a metre
    shore = ndi.binary_dilation(sea, iterations=1) & ~ndi.binary_erosion(sea, iterations=1)
    tol[shore] = np.minimum(tol[shore], 1.0)
    tol[inside] = np.inf
    # the inner edge: where the ground TIN's edges cross the ground area's outline (the ground layers end
    # there, straight between those points), plus the corners, heights from the ground TIN
    ex, ez, ey = edge_breaks(ground, (hx0, hz0, hx1, hz1))
    # [terrain] back_peaks: the named summits ([terrain.peaks] with a height) beyond the ground area pinned as TIN
    # vertices at their surveyed height (the FAR_CELL average flattened Teufelsberg's 120 m to 108); off by default
    if C.get("back_peaks", False):
        n_pk = 0
        for name, (lon, lat, real) in PEAKS.items():
            if real is None:
                continue
            px_, py_ = to_utm.transform(lon, lat)
            sx, sz = px_ - origin[0], -(py_ - origin[1])
            if hx0 - 1 <= sx <= hx1 + 1 and hz0 - 1 <= sz <= hz1 + 1:
                continue
            if not (X.min() < sx < X.max() and Z.min() < sz < Z.max()):
                continue
            yv = float(real) - (datum if datum is not None else 0.0)
            if CURVATURE:
                yv = float(curve(np.float64(yv), sx, sz))
            ex, ez, ey = np.r_[ex, sx], np.r_[ez, sz], np.r_[ey, yv]
            n_pk += 1
        log(f"backdrop: {n_pk} named summits pinned at their surveyed heights")
    init = (((ii % 25 == 0) & (jj % 25 == 0)) | (ii == 0) | (jj == 0) | (ii == nx - 1) | (jj == nz - 1)) & ~inside
    pts, y, tri = greedy_tin((nx, nz), Y, tol, init, extra=((ex - x0) / FAR_CELL, (ez - z0) / FAR_CELL, ey),
                             label="backdrop TIN")
    px, pz = x0 + pts[:, 0] * FAR_CELL, z0 + pts[:, 1] * FAR_CELL
    n_ex = len(ex)
    px[-n_ex:], pz[-n_ex:] = ex, ez                    # exactly, not through the grid units
    on = np.round(pts[:-n_ex]).astype(np.int64)
    # the heights before the curvature: the grid's at the TIN's own nodes, the extra points' as given
    h = np.r_[H[on[:, 1], on[:, 0]], uncurve(y[-n_ex:], ex, ez) if CURVATURE else y[-n_ex:]]
    seas = np.r_[sea[on[:, 1], on[:, 0]], np.zeros(n_ex, bool)]
    lakes = np.r_[lake[on[:, 1], on[:, 0]], np.zeros(n_ex, bool)]
    # drop the triangles over the ground area and those wholly on the sea
    cx, cz = px[tri].mean(1), pz[tri].mean(1)
    hole = (cx > hx0) & (cx < hx1) & (cz > hz0) & (cz < hz1)
    n_tin = len(tri)
    tri = tri[~hole & ~seas[tri].all(1)]
    used, inv = np.unique(tri, return_inverse=True)
    tri = inv.reshape(-1, 3)
    px, pz, y, lakes, h = px[used], pz[used], y[used], lakes[used], h[used]
    a, b, c = (np.stack([px[tri[:, k]], pz[tri[:, k]]], 1) for k in range(3))
    cross = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
    tri[cross > 0] = tri[cross > 0][:, [0, 2, 1]]
    colour = backdrop_colours(px, pz, y, tri, lakes, C["backdrop_town"], tuple(C["backdrop_forest"]), C["backdrop_town_rgb"])
    log(f"backdrop: {len(px):,} vertices, {len(tri):,} triangles over {(bx1 - bx0) / 1000:.0f} x "
        f"{(by1 - by0) / 1000:.0f} km (of the TIN's {n_tin:,}: those over the ground area and wholly on the sea "
        f"dropped) ({time.time() - t0:.0f} s)")
    out = {"back_xyz": np.stack([px, y, pz], 1).astype(np.float32), "back_tri": tri.astype(np.int32),
           "back_rgb": colour}
    if CURVATURE:
        out["back_h"] = h.astype(np.float32)
    return out


def back_sea_mask(dsm, zero, bare=False, void=None):
    """The backdrop's sea cells: the DEM about 0 (mean and nearest); with a bare-earth DEM all at or under 0.2 m
    (no data beyond the coast, hydro-flattened water a little under 0), or with `void` ([terrain] back_sea "void":
    where the bare file has no data) only those of them where it is void."""
    sea = (np.abs(dsm) < 0.3) & (np.abs(zero) < 0.01)
    if bare and void is not None:
        return void & (dsm < 0.2)
    if bare:
        sea |= dsm < 0.2
    return sea


def _drop(X, Z):
    """[terrain] curvature: the earth's drop (m) at scene (X, Z) as seen from the origin."""
    r = np.maximum(np.hypot(X, Z) - float(CURVATURE.get("from", 12000.0)), 0)
    return r * r / (2 * 6371000.0 / (1 - float(CURVATURE.get("k", 0.13))))


def curve(Y, X, Z):
    """Heights over the plain as seen past the curvature's drop: y^2 / (y + D), never under 0."""
    D = _drop(X, Z)
    return np.where(Y > 0, Y * Y / np.maximum(Y + D, 1e-6), Y)


def uncurve(Y, X, Z):
    """The inverse of curve: y = (y' + sqrt(y'^2 + 4 D y')) / 2."""
    D = _drop(X, Z)
    return np.where(Y > 0, (Y + np.sqrt(Y * Y + 4 * D * np.maximum(Y, 0))) / 2, Y)


def edge_breaks(ground, rect):
    """Points on the rectangle's outline where the ground TIN's edges cross it, and its corners, with the
    ground's height there."""
    x0, z0, x1, z1 = rect
    p, gy = ground["xz"], ground["y"]
    e = np.concatenate([ground["tri"][:, [0, 1]], ground["tri"][:, [1, 2]], ground["tri"][:, [2, 0]]])
    a, b, ya, yb = p[e[:, 0]], p[e[:, 1]], gy[e[:, 0]], gy[e[:, 1]]
    corners = np.array([[x0, z0], [x1, z0], [x1, z1], [x0, z1]])
    xs, zs, ys = [corners[:, 0]], [corners[:, 1]], [tin_height(ground, corners)]
    for axis, c, lo, hi in ((0, x0, z0, z1), (0, x1, z0, z1), (1, z0, x0, x1), (1, z1, x0, x1)):
        da, db = a[:, axis] - c, b[:, axis] - c
        hit = da * db < 0
        t = da[hit] / (da[hit] - db[hit])
        q = a[hit] + (b[hit] - a[hit]) * t[:, None]
        y = ya[hit] + (yb[hit] - ya[hit]) * t
        ok = (q[:, 1 - axis] > lo) & (q[:, 1 - axis] < hi)
        q, y = q[ok], y[ok]
        q[:, axis] = c
        xs.append(q[:, 0]); zs.append(q[:, 1]); ys.append(y)
    xs, zs, ys = np.concatenate(xs), np.concatenate(zs), np.concatenate(ys)
    _, first = np.unique(np.round(np.stack([xs, zs], 1), 2), axis=0, return_index=True)
    return xs[first], zs[first], ys[first]


def tin_height(ground, pts):
    """Heights of a few points on the ground TIN (a brute-force search of its triangles per point)."""
    p, gy, tri = ground["xz"], ground["y"], ground["tri"]
    a, b, c = p[tri[:, 0]], p[tri[:, 1]], p[tri[:, 2]]
    det = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
    out = []
    for x, z in pts:
        u = ((x - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (z - a[:, 1])) / det
        v = ((b[:, 0] - a[:, 0]) * (z - a[:, 1]) - (x - a[:, 0]) * (b[:, 1] - a[:, 1])) / det
        k = np.flatnonzero((u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9))
        k = k[0] if len(k) else int(np.argmin(np.hypot(a[:, 0] - x, a[:, 1] - z)))
        out.append(gy[tri[k, 0]] + u[k] * (gy[tri[k, 1]] - gy[tri[k, 0]]) + v[k] * (gy[tri[k, 2]] - gy[tri[k, 0]]))
    return np.array(out)


def backdrop_colours(X, Z, Y, tri, lakes, town_share=0.55, forest=(25.0, 85.0), town_rgb=(150, 146, 132)):
    """sRGB per vertex: forest on slopes and hills, towns and fields on the flats (town_share of them town,
    in patches kilometres across rather than vertex by vertex), dark water on lakes."""
    # slope from the triangles around each vertex (area-weighted normals)
    P = np.stack([X, Y, Z], 1)
    n = np.cross(P[tri[:, 1]] - P[tri[:, 0]], P[tri[:, 2]] - P[tri[:, 0]])
    vn = np.zeros_like(P)
    for k in range(3):
        np.add.at(vn, tri[:, k], n)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
    steep = np.clip((1 - np.abs(vn[:, 1])) / 0.06, 0, 1)             # 0 flat .. 1 at ~20 degrees
    high = np.clip((Y - forest[0]) / (forest[1] - forest[0]), 0, 1)     # wooded from forest[0] m, all by forest[1]
    wood = np.maximum(steep, high)
    rng = np.random.default_rng(3)
    jitter = rng.uniform(0.96, 1.04, len(X))[:, None]
    forest, town, field = np.array([62, 84, 52]), np.array(town_rgb), np.array([112, 122, 84])
    # low-frequency patches: a few sines of random direction, so towns and fields come in areas
    k = np.zeros(len(X))
    for _ in range(6):
        a, f, ph = rng.uniform(0, np.pi), rng.uniform(1 / 9000, 1 / 2500), rng.uniform(0, 2 * np.pi)
        k += np.sin((X * np.cos(a) + Z * np.sin(a)) * 2 * np.pi * f + ph)
    k = k / 6 + rng.normal(0, 0.08, len(X))
    t = np.clip((k - np.quantile(k, 1 - town_share)) / 0.15 + 0.5, 0, 1)[:, None]
    flat = town * t + field * (1 - t)
    rgb = (forest * wood[:, None] + flat * (1 - wood[:, None])) * jitter
    rgb[lakes] = [52, 66, 70]
    return np.clip(rgb, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- checks

def checks(T, dsm, tr, land, tin_info, back, datum=None):
    """checks/terrain.png (hillshade with the districts) and checks/terrain.md (summits)."""
    to = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    inv = ~tr
    rows = []
    for name, (lon, lat, real) in PEAKS.items():
        e, n = to.transform(lon, lat)
        c, r = inv * (e, n)
        c, r = int(c), int(r)
        rad = max(int(PEAK_R / WORK), 1)
        if 0 <= r < T.shape[0] and 0 <= c < T.shape[1]:
            win = np.s_[max(r - rad, 0):r + rad, max(c - rad, 0):c + rad]
            rows.append((name, real, float(np.nanmax(dsm[win])), float(T[win].max())))
        else:
            # beyond the ground area: the backdrop's vertices within 1.5 km
            xyz = back["back_xyz"]
            ox, oy = tin_info["origin"]
            d = np.hypot(xyz[:, 0] - (e - ox), xyz[:, 2] + (n - oy))
            near = d < max(PEAK_R, 300.0) if PEAK_R < 1000 else d < 1500
            rows.append((name, real, None, float(xyz[near, 1].max()) if near.any() else None))
    drop = f"the plain was dropped by about {SEA_DROP + SEA_KNEE:.0f} m to meet the sea at 0" if datum is None else \
        f"the ground was lowered by {datum:.1f} m (inland: its lowest point is 0)"
    bare = getattr(DEM_SOURCE, "BARE", False)
    dem_name = CFG["sources"]["dem"]
    lines = ["# Terrain (05a_terrain.py)", "",
             f"Summits: the highest point within {PEAK_R:g} m of each named peak in the DEM ({dem_name}"
             + (", bare earth)" if bare else ", a surface model: canopy and all)") + " and in the scene's ground after "
             + ("smoothing" if bare else "buildings, canopy and smoothing were taken off") + " and",
             f"{drop}. The viewer's trees",
             "(8-16 m on forest) stand on top of the ground again.", "",
             "| Summit | surveyed (m) | DEM (m) | scene ground (m) |", "|---|---|---|---|"]
    for name, real, d, t in rows:
        f = lambda v: "–" if v is None else f"{v:.0f}"
        lines.append(f"| {name} | {f(real)} | {f(d)} | {f(t)} |")
    if WATER_LEVELS:
        to_ll = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
        off = datum or 0.0
        lines += ["", f"Water levels (inland_water): the largest bodies; "
                  "level = the median of the ground under the body, held flat; spread = its 10th-90th percentile "
                  f"(over {FLAT_SPREAD:.0f} m: left on its slope). Scene y" + (f"; + datum {off:.1f} = m in the DEM's datum." if datum else "."),
                  "", "| Body (a point in it) | area (ha) | level, scene y (m) | in the DEM's datum (m) | spread p10-p90 (m) |",
                  "|---|---|---|---|---|"]
        for p, lv, lo, hi in sorted(WATER_LEVELS, key=lambda r: -r[0].area)[:25]:
            q = p.representative_point()
            lon, lat = to_ll.transform(q.x, q.y)
            f = lambda v: "sloping" if v is None else f"{v:.2f}"   # noqa: E731
            lines.append(f"| {lat:.5f}, {lon:.5f} | {p.area / 1e4:,.1f} | {f(lv)} | "
                         f"{'' if lv is None else f'{lv + off:.2f}'} | {lo:.2f}-{hi:.2f} |")
    lines += ["", *[f"- {m}" for m in LOG]]
    (CHECKS / "terrain.md").write_text("\n".join(lines) + "\n")

    # hillshade, 20 m pixels, sun from the north-west
    s = 2
    t = T[::s, ::s].astype(np.float64)
    gz, gx = np.gradient(t, WORK * s)
    az, alt = np.radians(315), np.radians(40)
    slope = np.arctan(np.hypot(gx, gz))
    aspect = np.arctan2(-gx, gz)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    lm = land[::s, ::s]
    fig, ax = plt.subplots(figsize=(10, 14))
    ax.imshow(np.where(lm, shade, np.nan), cmap="gray", vmin=0, vmax=1)
    # the tint over the scene's own range: the ground's and the backdrop's (pinned summits included), not 0-600 m
    # (Berlin M7 critic: a 0-69 m ground tinted on a 0-600 m scale showed no relief at all)
    top = max(float(t.max()), float(back["back_xyz"][:, 1].max()) if back is not None else 0.0)
    vmax = float(np.ceil(max(top, 10.0) / 10) * 10)
    ax.imshow(np.where(lm & (t > 0), t, np.nan), cmap="terrain", alpha=0.45, vmin=-0.1 * vmax, vmax=vmax)
    ax.set_facecolor("#9db7c9")
    d = boundary().boundary.iloc[0]
    for part in getattr(d, "geoms", [d]):
        xy = np.asarray(part.coords)
        cc, rr = inv * (xy[:, 0], xy[:, 1])
        ax.plot(np.asarray(cc) / s, np.asarray(rr) / s, color="#c0392b", lw=0.8)
    for name, (lon, lat, _) in PEAKS.items():
        e, n = to.transform(lon, lat)
        cc, rr = inv * (e, n)
        if 0 <= rr < T.shape[0] and 0 <= cc < T.shape[1]:
            ax.plot(cc / s, rr / s, "^", color="#222", ms=4)
            ax.annotate(name.split(" ", 1)[-1], (cc / s, rr / s), fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.set_title(f"Scene ground (05a_terrain.py): hillshade, height tint 0-{vmax:.0f} m; TIN {tin_info['tris']:,} triangles")
    ax.set_axis_off()
    fig.savefig(CHECKS / "terrain.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- main

def lift_summits(g, tr, drop, held=None):
    """[terrain] summits: each named peak inside the grid whose ground (the highest within peak_radius, at most 150 m)
    lies under its surveyed height less `drop` lifted to it (in place); returns [(name, before, after)]."""
    R = float(SUMMITS.get("radius", 500.0))
    to = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    inv = ~tr
    out = []
    rad = int(R / WORK)
    for name, (lon, lat, real) in PEAKS.items():
        if real is None:
            continue
        c, r = inv * to.transform(lon, lat)
        c, r = int(c), int(r)
        if not (rad <= r < g.shape[0] - rad and rad <= c < g.shape[1] - rad):
            continue
        win = np.s_[r - rad:r + rad + 1, c - rad:c + rad + 1]
        sub = g[win]
        jj, ii = np.mgrid[-rad:rad + 1, -rad:rad + 1]
        d = np.hypot(ii, jj) * WORK
        near = d <= min(PEAK_R, 150.0)
        k = np.flatnonzero(near.ravel())[np.argmax(sub[near])]
        top = float(sub.flat[k])
        target = float(real) - drop
        if top >= target - 0.5:
            out.append((name, top, top))
            continue
        # (round the hill's own top, not the point given)
        tj, ti = np.unravel_index(k, sub.shape)
        d = np.hypot(ii - (ti - rad), jj - (tj - rad)) * WORK
        disk = d <= R
        foot = float(np.percentile(sub[disk], 5))
        if top - foot < 5.0:
            out.append((name, top, top))
            continue
        w = np.clip((R - d) / (R * 2 / 3), 0, 1)
        w = w * w * (3 - 2 * w)
        if held is not None:
            w = w * ~held[win]                      # levelled water stays level
        scale = (target - foot) / (top - foot)
        sub += (w * (scale - 1) * np.clip(sub - foot, 0, None)).astype(sub.dtype)
        out.append((name, top, float(sub.flat[k])))
    log("summits: " + ", ".join(f"{n} {a:.0f} -> {b:.0f} m" for n, a, b in out))
    return out


def main():
    t0 = time.time()
    b = boundary()
    x0b, y0b, x1b, y1b = b.total_bounds
    origin = ((x0b + x1b) / 2, (y0b + y1b) / 2)              # 06_tiles.py's scene origin
    area = gpd.read_file(DATA / "ground.gpkg", layer="area").geometry.iloc[0]
    # the grid starts on a TIN_CELL node so the TIN's vertices are every other WORK node
    x0, z0, nx, nz, _ = scene_grid(origin, area.bounds, TIN_CELL)
    nx, nz = (nx - 1) * int(TIN_CELL / WORK) + 1, (nz - 1) * int(TIN_CELL / WORK) + 1
    tr = Affine(WORK, 0, origin[0] + x0 - WORK / 2, 0, -WORK, origin[1] - z0 + WORK / 2)
    shape = (nz, nx)
    log(f"work grid {nx} x {nz} at {WORK:.0f} m")

    dsm = dem_on(tr, shape, Resampling.bilinear)
    dsm = gap_fill(dsm, tr, shape)
    if getattr(DEM_SOURCE, "BARE", False):
        g = bare_smooth(dsm)
        dsm = np.nan_to_num(dsm)
    else:
        dsm = np.nan_to_num(dsm)
        g = bare_earth(dsm, tr, origin)
    land_g = gpd.read_file(DATA / "ground.gpkg", layer="land").geometry
    aero = gpd.read_file(DATA / "ground.gpkg", layer="aeroway").geometry
    land = burn(shape, tr, list(land_g) + list(aero)).astype(bool)
    if EDGE_LAND:
        inner = ndi.binary_erosion(burn(shape, tr, [area]).astype(bool), iterations=EDGE_LAND_CELLS)
        idx = ndi.distance_transform_edt(~inner, return_distances=False, return_indices=True)
        n_edge = int((land[idx[0], idx[1]] & ~land).sum())
        land = land[idx[0], idx[1]]
        log(f"edge_land: {n_edge:,} cells along the area's edge taken as land")
    water_l = gpd.read_file(DATA / "ground.gpkg", layer="water")
    pooled = "pool" in water_l.columns
    water = water_l.geometry
    if PITS or CUTTINGS:
        wet = burn(shape, tr, list(water.make_valid())).astype(bool) | ~land
        if PITS:
            fill_pits(g, tr, wet)
        fill_cuttings(g, tr, wet)
        del wet
    datum = None
    if coastal(area, land_g):
        to_sea = (ndi.distance_transform_edt(land) * WORK).astype(np.float32)
        g = sea_drop(g) * coast_ramp(to_sea)
        held, n_flat, n_slope = inland_water(g, tr, list(water.make_valid()), pooled)
        g[(to_sea <= COAST_FLAT) | ~land] = 0                 # water levelled right by the sea keeps the coast at 0
        coast = land & (to_sea <= COAST_FLAT)
        del to_sea
    else:
        # inland: nothing to meet, only lowered so the lowest ground is 0
        datum = float(g[land].min() if DATUM == "auto" else DATUM)
        g = np.maximum(g - datum, 0).astype(np.float32)
        held, n_flat, n_slope = inland_water(g, tr, list(water.make_valid()), pooled)
        coast = np.zeros_like(land)
        log(f"inland: no sea in the ground area, ground lowered by {datum:.1f} m")
    log(f"inland water: {n_flat} bodies levelled, {n_slope} left on their slope ({time.time() - t0:.0f} s)")
    if SUMMITS:
        lift_summits(g, tr, SEA_DROP + SEA_KNEE if datum is None else datum, held)
    patches(g, tr)
    dalles(g, tr, held)
    keep = deck_ends(g, tr, list(water.make_valid()))

    bank = None
    if TIN_ERROR_BANK:
        bank = ndi.distance_transform_edt(~held) * WORK <= BANK_REACH
    ij, y, tri = ground_tin(g, origin, x0, z0, held | coast, bank, keep)
    log(f"ground TIN: {len(y):,} vertices, {len(tri):,} triangles, heights 0-{y.max():.0f} m ({time.time() - t0:.0f} s)")
    ground = {"xz": np.stack([x0 + ij[:, 0] * TIN_CELL, z0 + ij[:, 1] * TIN_CELL], 1).astype(np.float64),
              "y": y.astype(np.float64), "tri": tri}
    back = backdrop(origin, area.bounds, ground, datum)

    extra = {} if datum is None else {"datum": np.float64(datum)}
    np.savez_compressed(TERRAIN, origin=np.array(origin), cell=TIN_CELL, x0=x0, z0=z0, ij=ij, y=y, tri=tri, **back,
                        **extra)
    checks(g, dsm, tr, land, {"tris": len(tri), "origin": origin}, back, datum)
    log(f"done ({time.time() - t0:.0f} s)")

