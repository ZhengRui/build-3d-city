"""Source adapter: IGN's bare-earth elevation for France (Licence Ouverte / Etalab 2.0, "Source : IGN").

  ground    the LiDAR HD MNT (a 1 m terrain model from the ground-classified points of IGN's national lidar
            survey, heights in metres over NGF-IGN69, the French levelling datum), filled from the RGE ALTI 5 m
            where the lidar has no ground (see below)
  backdrop  RGE ALTI (bare earth, 1-5 m, hydro-flattened rivers) at [sources.ign] cells.backdrop metres, out to
            terrain.far_reach beyond the ground area: the same datum as the ground, so the two meet without a
            step and no towns stand in the hills as lumps

Both are bare earth (BARE): 05a_terrain skips its building masking, opening and canopy steps and only smooths
lightly (terrain.smooth_bare).

Fetching (stage 02_dem): the raw rasters are read from raw/ ([sources.ign] ground, fill, backdrop: paths in
raw/, Lambert-93, float32, no data -9999). Missing ones are fetched from the Géoplateforme's WMS-Raster
(https://data.geopf.fr/wms-r/wms, open, no key) as image/x-bil;bits=32 in 2000 px blocks over the ground area
(the districts' box plus ground.margin plus a kilometre) or the backdrop's (plus terrain.far_reach and 2 km),
3 requests at a time; layers [sources.ign] layers.

Preparing: each is warped from Lambert-93 to the city's UTM zone (average resampling onto [sources.ign] cell
metres for the ground: 05a_terrain works on 10 m) and written as raw/ign_ground.tif and raw/ign_backdrop.tif,
the files tiles() returns. The lidar's defects are filled from the RGE ALTI there:
  voids   where no ground points were classified (Paris: the Mont-Valérien fort, 150,000 m², interpolated
          flat at 137 m for ~162 m) the lidar model is a flat TIN surface well under the ground;
  pits    shafts and trenches (Paris: ~5,000 pixels at 1 m, down to −6.9 m).
On the ground grid, a cell is filled where its lowest 1 m lidar value is under pit_below m or its mean is
under the RGE ALTI by more than pit_diff m (with its neighbours: pits), and in every connected region where the
lidar is under the RGE ALTI by more than pit_grow m and on average by more than pit_diff m (voids: the whole
region, so a void's rim doesn't leave a step). Forests are left alone: the RGE ALTI, older and partly
photogrammetric, stands a few metres over the lidar under trees (Saint-Cloud, Meudon: 3-7 m over whole
hillsides), which is its error, not the lidar's. Only lower is filled:
where the lidar is higher than the older RGE ALTI it is newer earthworks (Paris: La Défense's dalle, +14 m;
the Clamart spoil heap), which are real. The filled pixels are listed in raw/ign_fill.json for checks/dem.md.
"""
import json
import time

import numpy as np
import rasterio
import requests
from rasterio.transform import from_origin

from ..common import CFG, HEADERS, RAW, UTM, boundary

URL = "https://data.geopf.fr/wms-r/wms"
C = CFG["sources"]["ign"]
BARE = True
NODATA = -9999.0
BLOCK = 2000
FILES = {"ground": RAW / "ign_ground.tif", "backdrop": RAW / "ign_backdrop.tif"}
FILL_LOG = RAW / "ign_fill.json"


def tiles(role: str = "ground") -> list:
    return [FILES[role]]


def extent(role: str = "ground") -> tuple:
    """(west, south, east, north) in degrees covered by the file."""
    import rasterio.warp
    with rasterio.open(FILES[role]) as r:
        w, s, e, n = rasterio.warp.transform_bounds(r.crs, "EPSG:4326", *r.bounds)
    return float(w), float(s), float(e), float(n)


def raw(key: str):
    return RAW / C[key]


def area(role: str, crs: str, align: float = 100.0) -> tuple:
    """The box to cover in crs: the districts' box plus the ground margin and a kilometre (ground), or plus
    terrain.far_reach and 2 km (backdrop), snapped outwards to align metres."""
    from pyproj import Transformer
    pad = CFG["ground"]["margin"] + (1000.0 if role == "ground" else CFG["terrain"]["far_reach"] + 2000.0)
    x0, y0, x1, y1 = boundary().total_bounds
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    if crs != UTM:
        t = Transformer.from_crs(UTM, crs, always_xy=True)
        xs, ys = t.transform([x0, x1, x0, x1, (x0 + x1) / 2, (x0 + x1) / 2], [y0, y0, y1, y1, y0, y1])
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    return (np.floor(x0 / align) * align, np.floor(y0 / align) * align,
            np.ceil(x1 / align) * align, np.ceil(y1 / align) * align)


# ---------------------------------------------------------------- the WMS-Raster

def wms_block(layer, x0, y0, x1, y1, w, h, tries=8):
    """One GetMap request as float32 (no data -9999); BBOX are pixel edges in Lambert-93 (x, y order)."""
    p = dict(SERVICE="WMS", VERSION="1.3.0", REQUEST="GetMap", LAYERS=layer, STYLES="", CRS=C["crs"],
             BBOX=f"{x0},{y0},{x1},{y1}", WIDTH=w, HEIGHT=h, FORMAT="image/x-bil;bits=32")
    for k in range(tries):
        try:
            r = requests.get(URL, params=p, headers=HEADERS, timeout=600)
            r.raise_for_status()
            if len(r.content) != w * h * 4:
                raise RuntimeError(f"answer {r.headers.get('content-type')} {len(r.content)} bytes: {r.content[:200]!r}")
            a = np.frombuffer(r.content, "<f4").reshape(h, w).astype(np.float32)
            a[(a < -500) | ~np.isfinite(a)] = NODATA        # bilinear edges next to no data give ~ -9000
            return a
        except (requests.RequestException, RuntimeError) as e:
            if k == tries - 1:
                raise
            print(f"  retry {k + 1} after: {e}", flush=True)
            time.sleep(10 * (k + 1))


def wms_fetch(key: str, role: str):
    """raw/<[sources.ign] key> from the WMS, at cells.<key> m over the role's area, resumable by block."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    out, layer, cell = raw(key), C["layers"][key], float(C["cells"][key])
    x0, y0, x1, y1 = area(role, C["crs"])
    w, h = int(round((x1 - x0) / cell)), int(round((y1 - y0) / cell))
    print(f"WMS {layer}: {w} x {h} px at {cell} m", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_suffix(".part.tif")
    done_f = out.with_suffix(".done")
    done = set(json.loads(done_f.read_text())) if done_f.exists() and part.exists() else set()
    if not part.exists():
        with rasterio.open(part, "w", driver="GTiff", width=w, height=h, count=1, dtype="float32", crs=C["crs"],
                           transform=from_origin(x0, y1, cell, cell), nodata=NODATA, compress="deflate",
                           predictor=3, tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES"):
            pass
    jobs = [(r0, c0) for r0 in range(0, h, BLOCK) for c0 in range(0, w, BLOCK) if f"{r0},{c0}" not in done]

    def one(rc):
        r0, c0 = rc
        bh, bw = min(BLOCK, h - r0), min(BLOCK, w - c0)
        bx0, by1 = x0 + c0 * cell, y1 - r0 * cell
        return rc, wms_block(layer, bx0, by1 - bh * cell, bx0 + bw * cell, by1, bw, bh)

    with rasterio.open(part, "r+") as dst, ThreadPoolExecutor(3) as ex:
        for n, f in enumerate(as_completed([ex.submit(one, j) for j in jobs]), 1):
            (r0, c0), a = f.result()
            dst.write(a, 1, window=rasterio.windows.Window(c0, r0, a.shape[1], a.shape[0]))
            done.add(f"{r0},{c0}")
            done_f.write_text(json.dumps(sorted(done)))
            print(f"  [{n}/{len(jobs)}] block r{r0} c{c0}", flush=True)
    part.rename(out)
    done_f.unlink(missing_ok=True)


# ---------------------------------------------------------------- warping and filling

def warp(path, grid, resampling):
    """path warped onto grid (transform, width, height in UTM) with resampling; no data NaN."""
    from rasterio.vrt import WarpedVRT
    tr, w, h = grid
    with rasterio.open(path) as src, WarpedVRT(src, crs=UTM, transform=tr, width=w, height=h, resampling=resampling,
                                               src_nodata=src.nodata, nodata=np.nan, dtype="float32",
                                               warp_mem_limit=512) as vrt:
        return vrt.read(1)


def write(path, a, tr):
    with rasterio.open(path, "w", driver="GTiff", width=a.shape[1], height=a.shape[0], count=1, dtype="float32",
                       crs=UTM, transform=tr, nodata=NODATA, compress="deflate", predictor=3, tiled=True) as dst:
        dst.write(np.where(np.isfinite(a), a, NODATA).astype(np.float32), 1)


def fill_defects(lid, lid_min, ref, tr, cell):
    """The lidar with its voids and pits replaced by the reference (module docstring); and what was filled."""
    from pyproj import Transformer
    from scipy import ndimage as ndi
    d = lid - ref
    # pits: a cell whose lowest 1 m value is under pit_below, or whose mean is under the reference by pit_diff,
    # and its neighbours; voids: a region under the reference by pit_grow or more whose mean is pit_diff under
    pit = (lid_min < C["pit_below"]) | (d < -C["pit_diff"]) | (np.isnan(lid) & np.isfinite(ref))
    pit = ndi.binary_dilation(pit, iterations=1)
    lab, n = ndi.label(d < -C["pit_grow"])
    mean = ndi.mean(d, lab, np.arange(1, n + 1)) if n else np.array([])
    void = np.isin(lab, np.flatnonzero(mean < -C["pit_diff"]) + 1)
    bad = pit | void
    out = np.where(bad & np.isfinite(ref), ref, lid)
    to = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    blobs = []
    lb, nb = ndi.label(bad)
    if nb:
        idx = np.arange(1, nb + 1)
        size = ndi.sum(bad, lb, idx)
        low = ndi.minimum(np.where(bad, lid_min, np.inf), lb, idx)
        dmean = ndi.mean(np.nan_to_num(d), lb, idx)
        cy, cx = np.array(ndi.center_of_mass(bad, lb, idx)).T
        for k in np.argsort(-size)[:15]:
            x, y = tr * (cx[k] + 0.5, cy[k] + 0.5)
            lon, lat = to.transform(x, y)
            blobs.append({"lon": round(lon, 5), "lat": round(lat, 5), "m2": float(size[k] * cell * cell),
                          "lidar_min": round(float(low[k]), 1), "lidar_minus_rge": round(float(dmean[k]), 1)})
    lo = np.nanargmin(np.where(bad, np.nan, lid))
    x, y = tr * (lo % lid.shape[1] + 0.5, lo // lid.shape[1] + 0.5)
    lon, lat = to.transform(x, y)
    info = {"cells_filled": int(bad.sum()), "m2_filled": float(bad.sum() * cell * cell), "regions": int(nb),
            "seeds_below": int((lid_min < C["pit_below"]).sum()), "largest": blobs,
            "lowest_kept": [round(float(lid.flat[lo]), 2), round(lon, 5), round(lat, 5)],
            "lidar_above_rge_8m_m2": float(((d > 8) & ~bad).sum() * cell * cell)}
    return out, info


def footprints_mask(tr, shape):
    """Every footprint source's buildings (and OSM's) that 01/02 have written, burnt onto the grid."""
    import geopandas as gpd
    import rasterio.features
    from ..common import DATA
    names = dict.fromkeys(list(CFG["sources"]["footprints"]) + ["osm"])
    mask = np.zeros(shape, np.uint8)
    used = []
    for n in names:
        f = DATA / f"{n}_buildings.gpkg"
        if not f.exists():
            continue
        g = gpd.read_file(f, columns=[]).to_crs(UTM).geometry
        g = g[g.notna() & ~g.is_empty]
        rasterio.features.rasterize(((geom, 1) for geom in g), out=mask, transform=tr)
        used.append(f"{n} ({len(g):,})")
    return mask.astype(bool), used


def unbake(a, ref, tr, cell):
    """Structures the lidar's ground classification kept (the Grande Arche's cube as a 100 m peak, La Défense
    Arena's roof, the Vincennes zoo's Grand Rocher, some Paris blocks as 30 m plateaus), which the RGE ALTI
    doesn't have (it agrees with the lidar within a metre on the hills: Montmartre, Chaillot, Belleville).
    Cells on a building footprint where the lidar stands more than [sources.ign] unbake metres over both the
    RGE ALTI and the grey opening of the ground (a window of unbake_open m, wider than any such structure) seed
    a region, grown over the footprints while the lidar is more than unbake_grow over the RGE ALTI (and two cells
    round them, the 5 m averaging's rim, while more than unbake over it); the region takes the RGE ALTI's height. Ground higher than its
    surroundings but no footprint's, or not higher than the RGE ALTI (hills, spoil heaps, La Défense's dalle),
    is kept. Returns the ground and the largest regions with their heights before and after."""
    from pyproj import Transformer
    from scipy import ndimage as ndi
    if not C.get("unbake"):
        return a, {}
    t0 = time.time()
    foot, used = footprints_mask(tr, a.shape)
    if not foot.any():
        return a, {"unbaked_sources": []}
    f = np.where(np.isfinite(a), a, np.nanmin(a)).astype(np.float32)
    px = int(C["unbake_open"] / cell) | 1
    rise = f - ndi.maximum_filter(ndi.minimum_filter(f, size=px), size=px)
    over = np.nan_to_num(f - ref, nan=0.0)
    near = ndi.binary_dilation(foot, iterations=2)
    # the rim round a footprint only where it stands well over the RGE ALTI (the averaging's smear of a tower),
    # not where the dalle round a building is a few metres over the older model's street
    lab, n = ndi.label((foot & (over > C["unbake_grow"])) | (near & (over > C["unbake"])))
    seeds = np.unique(lab[foot & (rise > C["unbake"]) & (over > C["unbake"])])
    seeds = seeds[seeds > 0]
    bad = np.isin(lab, seeds) & np.isfinite(ref)
    info = {"unbaked_sources": used, "unbaked_m2": float(bad.sum() * cell * cell), "unbaked_regions": int(len(seeds)),
            "unbaked": []}
    if not bad.any():
        return a, info
    out = np.where(bad, ref, a).astype(np.float32)
    to = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    lb, nb = ndi.label(bad)
    ids = np.arange(1, nb + 1)
    size = ndi.sum(bad, lb, ids)
    top = ndi.maximum(f, lb, ids)
    after = ndi.maximum(out, lb, ids)
    peak = ndi.maximum(over, lb, ids)
    cy, cx = np.array(ndi.center_of_mass(bad, lb, ids)).reshape(-1, 2).T
    for k in np.argsort(-(peak * np.sqrt(size)))[:20]:
        x, y = tr * (cx[k] + 0.5, cy[k] + 0.5)
        lon, lat = to.transform(x, y)
        info["unbaked"].append({"lon": round(lon, 5), "lat": round(lat, 5), "m2": float(size[k] * cell * cell),
                                "before": round(float(top[k]), 1), "after": round(float(after[k]), 1),
                                "rise": round(float(peak[k]), 1)})
    print(f"unbaked: {len(seeds)} structures over {bad.sum() * cell * cell / 1e4:.1f} ha on the footprints of "
          f"{', '.join(used)} ({time.time() - t0:.0f} s)", flush=True)
    return out, info


def prepare(role: str):
    """raw/ign_<role>.tif in UTM from the raw Lambert-93 rasters."""
    from rasterio.warp import Resampling
    import rasterio.warp
    t0 = time.time()

    def box(key, role, cell):
        """The role's area in UTM, within the raw file's own extent (a Lambert-93 box's corners are not a
        UTM box's)."""
        x0, y0, x1, y1 = area(role, UTM, cell)
        with rasterio.open(raw(key)) as r:
            bx0, by0, bx1, by1 = rasterio.warp.transform_bounds(r.crs, UTM, *r.bounds)
        x0, y0 = max(x0, np.ceil(bx0 / cell) * cell), max(y0, np.ceil(by0 / cell) * cell)
        x1, y1 = min(x1, np.floor(bx1 / cell) * cell), min(y1, np.floor(by1 / cell) * cell)
        w, h = int(round((x1 - x0) / cell)), int(round((y1 - y0) / cell))
        return from_origin(x0, y0 + h * cell, cell, cell), w, h

    if role == "backdrop":
        cell = float(C["cells"]["backdrop"])
        tr, w, h = box("backdrop", role, cell)
        a = warp(raw("backdrop"), (tr, w, h), Resampling.bilinear)
        write(FILES[role], a, tr)
        print(f"{FILES[role].name}: {w} x {h} at {cell:.0f} m, {np.nanmin(a):.1f}..{np.nanmax(a):.1f} m, "
              f"{np.isnan(a).mean():.2%} no data ({time.time() - t0:.0f} s)")
        return
    cell = float(C["cell"])
    tr, w, h = box("ground", role, cell)
    grid = (tr, w, h)
    lid = warp(raw("ground"), grid, Resampling.average)
    print(f"lidar averaged onto {w} x {h} at {cell:.0f} m ({time.time() - t0:.0f} s)", flush=True)
    lid_min = warp(raw("ground"), grid, Resampling.min)
    print(f"... and its lowest values ({time.time() - t0:.0f} s)", flush=True)
    ref = warp(raw("fill"), grid, Resampling.bilinear)
    out, info = fill_defects(lid, lid_min, ref, tr, cell)
    del lid_min
    out, baked = unbake(out, ref, tr, cell)
    info |= baked
    ok = np.isfinite(lid) & np.isfinite(ref)
    q = np.percentile((lid - ref)[ok], [5, 50, 95])
    info |= {"cell": cell, "lidar_minus_rge_p5_p50_p95": [round(float(v), 2) for v in q],
             "min_after": round(float(np.nanmin(out)), 2), "nodata_after": float(np.isnan(out).mean())}
    write(FILES[role], out, tr)
    FILL_LOG.write_text(json.dumps(info, indent=1))
    print(f"{FILES[role].name}: {w} x {h}, {np.nanmin(out):.1f}..{np.nanmax(out):.1f} m; filled from RGE ALTI: "
          f"{info['m2_filled'] / 1e4:.1f} ha in {info['regions']} regions ({time.time() - t0:.0f} s)")


def fetch(role: str = "ground"):
    keys = ["ground", "fill"] if role == "ground" else ["backdrop"]
    for k in keys:
        if not raw(k).exists():
            wms_fetch(k, role)
    newest = max(raw(k).stat().st_mtime for k in keys)
    if FILES[role].exists() and FILES[role].stat().st_mtime > newest:
        print(f"{FILES[role].name}: already prepared (delete it to warp and fill again)")
        return
    prepare(role)


def notes() -> list:
    """For checks/dem.md: the datum and the fill."""
    L = ["IGN heights are metres over NGF-IGN69 (the French levelling datum, mean sea level at Marseille). The "
         "scene is inland: 05a_terrain lowers the ground by terrain.datum so the lowest real ground is 0 and "
         "the viewer's sea plane stays under it. Ground: LiDAR HD MNT (1 m) averaged onto a "
         f"{C['cell']:.0f} m UTM grid, voids and pits filled from RGE ALTI 5 m; backdrop: RGE ALTI at "
         f"{C['cells']['backdrop']:.0f} m. Both bare earth.", ""]
    if FILL_LOG.exists():
        f = json.loads(FILL_LOG.read_text())
        p = f["lidar_minus_rge_p5_p50_p95"]
        L += [f"LiDAR HD − RGE ALTI over the ground area ({f['cell']:.0f} m cells): p5 {p[0]:+.2f} m, median "
              f"{p[1]:+.2f}, p95 {p[2]:+.2f}. Filled from RGE ALTI: {f['m2_filled'] / 1e4:.1f} ha in "
              f"{f['regions']} regions ({f['seeds_below']} cells with a 1 m value under {C['pit_below']:.0f} m). "
              f"The lidar stands more than 8 m over RGE ALTI on {f['lidar_above_rge_8m_m2'] / 1e4:.1f} ha, left as "
              "it is (newer earthworks and slabs). Lowest ground after the fill: "
              f"{f['min_after']:.1f} m.", "", "| Largest filled regions | lon, lat | area (m²) | lidar lowest (m) | "
              "lidar − RGE ALTI, mean (m) |", "|---|---|---|---|---|"]
        for k, b in enumerate(f["largest"][:10], 1):
            L.append(f"| {k} | {b['lon']}, {b['lat']} | {b['m2']:,.0f} | {b['lidar_min']:.1f} | {b['lidar_minus_rge']:+.1f} |")
        L.append("")
        if f.get("unbaked") is not None:
            L += [f"Buildings baked into the lidar's ground (structures its ground class kept): cells on a footprint "
                  f"({', '.join(f['unbaked_sources'])}) more than {C['unbake']:.0f} m over both the RGE ALTI and the "
                  f"ground's {C['unbake_open']:.0f} m opening, grown over the footprints while {C['unbake_grow']:.0f} m "
                  f"over the RGE ALTI, which fills them: {f['unbaked_regions']} regions, {f['unbaked_m2'] / 1e4:.1f} ha. "
                  "Ground higher than its surroundings off the footprints, or no higher than the RGE ALTI (hills, "
                  "spoil heaps, La Défense's dalle), is kept.", "",
                  "| Largest removed | lon, lat | area (m²) | highest before (m) | highest after (m) | "
                  "lidar over RGE ALTI (m) |", "|---|---|---|---|---|---|"]
            for k, b in enumerate(f["unbaked"][:15], 1):
                L.append(f"| {k} | {b['lon']}, {b['lat']} | {b['m2']:,.0f} | {b['before']:.1f} | {b['after']:.1f} | "
                         f"{b['rise']:+.1f} |")
            L.append("")
    return L
