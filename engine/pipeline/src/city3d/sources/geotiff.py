"""Source adapter "geotiff": elevation from local GeoTIFF files, any CRS, for a city whose DEM is already on disk
(London: Carbon & Place's GBDEM, a bare-earth mosaic of the Environment Agency's lidar, cut from its web-mercator
tiles; any national DTM downloaded by hand).

[sources.geotiff]:
  ground    files (in raw/, or absolute; glob patterns too, e.g. Berlin's "dgm1/dgm1_33_*_2_be_2025.tif") covering the ground area (the districts' box plus ground.margin)
  backdrop  files for the hills beyond (terrain.far_reach); empty: the ground's
  bare      true (default) when bare earth, so 05a_terrain skips its building masking, opening and canopy
            steps; false for a surface model
  note      a line for checks/dem.md (the product, its vertical datum, its resolution)

An entry may also be a table {path = "dtm/x.tif", shift = -1.3}: the file (or glob) with a vertical shift in metres
added to its heights wherever it is read (05a_terrain, 02_dem's report): a coastal city's datum offset (Hong Kong's
Principal Datum lies 1.30 m under mean sea level, the scene's sea at 0) without a prepared copy. A file with a shift
is warped on its own, apart from its neighbours in the list (each run of files of one CRS and one shift). `shift`
works on an archive table too (a file without a nodata value: use [terrain] dem_window, or merge's 0 between its
tiles is shifted too). No shift anywhere: the files are read as before.

An entry may also be a table naming rasters inside a zip archive, read in place through GDAL's /vsizip/ (no
unpacked copy): {archive = "terrain/os_terrain50/terr50_gagg_gb.zip", members = ["data/tq/*.zip"], ext = ".asc"}.
`members` are glob patterns of the archive's entries; an entry that is itself a zip (OS Terrain 50's one zip per
10 km square) is opened in turn and its files ending in `ext` are taken. London (M7): the Carbon & Place mosaic
first, OS Terrain 50 (50 m, OS OpenData) beyond it, where the mosaic ends 25-29 km out.

Files in different CRSs may be mixed: 05a_terrain (terrain.dem_on) warps each CRS's mosaic onto its grid in turn,
an earlier entry's data winning over a later one's, so a coarse national DTM only fills where the first one ends.

The files are used as they are: 05a_terrain mosaics and warps them onto its own UTM grid (terrain.dem_on), so
there is no prepared copy. Their nodata value is honoured. 02_dem only checks that they exist and reports them.
"""
from pathlib import Path

from ..common import CFG, RAW

C = {"ground": [], "backdrop": [], "bare": True, "note": "", **CFG["sources"].get("geotiff", {})}
BARE = bool(C["bare"])


def _archive(spec: dict) -> list:
    """GDAL paths of the rasters a zip archive holds (see the module docstring)."""
    import fnmatch
    import io
    import zipfile
    zp = Path(spec["archive"])
    zp = (zp if zp.is_absolute() else RAW / zp).absolute()
    pats = spec.get("members", ["*"])
    pats = [pats] if isinstance(pats, str) else list(pats)
    ext = spec.get("ext", ".tif").lower()
    out = []
    with zipfile.ZipFile(zp) as z:
        for name in sorted(z.namelist()):
            if not any(fnmatch.fnmatch(name, p) for p in pats):
                continue
            if name.lower().endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(z.read(name))) as inner:
                    out += [f"/vsizip//vsizip/{zp}/{name}/{n}" for n in sorted(inner.namelist())
                            if n.lower().endswith(ext)]
            elif name.lower().endswith(ext):
                out.append(f"/vsizip/{zp}/{name}")
    if not out:
        raise FileNotFoundError(f"[sources.geotiff] {zp}: no {ext} files match {pats}")
    return out


_CACHE = {}
SHIFTS = {}           # str(path) -> metres, from entries {path, shift} / {archive, ..., shift}


def _paths(v) -> list:
    v = [v] if isinstance(v, (str, dict)) else list(v)
    out = []
    for p in v:
        if isinstance(p, dict) and "archive" not in p:      # {path, shift}
            got = _paths(p["path"])
            for q in got:
                if p.get("shift"):
                    SHIFTS[str(q)] = float(p["shift"])
            out += got
        elif isinstance(p, dict):
            key = repr(sorted(p.items()))
            if key not in _CACHE:
                _CACHE[key] = _archive(p)
            for q in _CACHE[key]:
                if p.get("shift"):
                    SHIFTS[str(q)] = float(p["shift"])
            out += _CACHE[key]
        elif p and any(c in p for c in "*?["):     # a glob pattern: its files in name order
            import glob
            hits = sorted(glob.glob(str(Path(p) if Path(p).is_absolute() else RAW / p)))
            if not hits:
                raise FileNotFoundError(f"[sources.geotiff] {p}: no files match")
            out += [Path(h) for h in hits]
        elif p:
            out.append(Path(p) if Path(p).is_absolute() else RAW / p)
    return out


def shifts() -> dict:
    """{str(path): metres} of every entry with a vertical shift (sources.geotiff_shifts)."""
    tiles("ground"), tiles("backdrop")
    return dict(SHIFTS)


def shift(path) -> float:
    """The vertical shift (m) of a file, 0 when its entry has none."""
    return SHIFTS.get(str(path), 0.0) if SHIFTS else 0.0


def tiles(role: str = "ground") -> list:
    """The files of a role ("ground" or "backdrop"; the backdrop falls back to the ground's)."""
    p = _paths(C["backdrop"]) if role == "backdrop" else []
    return p or _paths(C["ground"])


def extent(role: str = "ground") -> tuple:
    """(west, south, east, north) in degrees covered by the role's files together."""
    import rasterio
    import rasterio.warp
    key = ("extent", role)
    if key in _CACHE:
        return _CACHE[key]
    w = s = 999.0
    e = n = -999.0
    for p in tiles(role):
        with rasterio.open(p) as r:
            a, b, c, d = rasterio.warp.transform_bounds(r.crs, "EPSG:4326", *r.bounds)
        w, s, e, n = min(w, a), min(s, b), max(e, c), max(n, d)
    _CACHE[key] = (float(w), float(s), float(e), float(n))
    return _CACHE[key]


def fetch(role: str = "ground"):
    """Nothing to download: check the files are there and say what they are."""
    import rasterio
    files = tiles(role)
    if not files:
        raise FileNotFoundError(f"[sources.geotiff] {role}: no files configured")
    plain = [p for p in files if not str(p).startswith("/vsi")]
    for p in plain:
        if not p.exists():
            raise FileNotFoundError(f"[sources.geotiff] {role}: {p} is missing (put it in raw/ by hand)")
        with rasterio.open(p) as r:
            print(f"{p.name}: {r.width} x {r.height} px, {r.res[0]:.2f} x {r.res[1]:.2f} ({r.crs}), nodata {r.nodata}")
    if len(plain) < len(files):
        with rasterio.open(next(p for p in files if str(p).startswith("/vsi"))) as r:
            print(f"+ {len(files) - len(plain)} rasters in archives, e.g. {r.width} x {r.height} px, "
                  f"{r.res[0]:.2f} m ({r.crs.to_string()[:40]})")


def notes() -> list:
    """For checks/dem.md."""
    L = [C["note"], ""] if C["note"] else []
    def names(role):
        fs = tiles(role)
        plain = [Path(p).name for p in fs if not str(p).startswith("/vsi")]
        n = len(fs) - len(plain)
        return ", ".join(plain + ([f"{n} rasters from archives"] if n else []))
    return L + [f"geotiff: ground {names('ground')}; backdrop {names('backdrop')}; "
                f"{'bare earth' if BARE else 'a surface model'}.", ""]
