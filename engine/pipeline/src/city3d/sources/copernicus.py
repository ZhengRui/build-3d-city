"""Source adapter: the Copernicus GLO-30 DEM (1 arcsecond, heights over EGM2008; a surface model: roofs and
canopy included), the terrain's input (05a_terrain) worldwide.

Tiles are 1 x 1 degree COGs named Copernicus_DSM_COG_10_<N22_00_E113_00>_DEM.tif, downloaded into raw/
(AWS open data: s3://copernicus-dem-30m/<name without .tif>/<name>, no account needed). [sources.copernicus]
tiles lists them ("N22_00_E113_00", ...); left empty, every such tile in raw/ is used. They must cover the
ground area; the backdrop (terrain.far_reach beyond it) is cut to what they cover. fetch() (stage 02_dem)
downloads the listed tiles, or with none listed every tile the ground area plus the backdrop reaches.
"""
import math
import re

import requests

from ..common import CFG, HEADERS, RAW

BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"
BARE = False

PREFIX, SUFFIX = "Copernicus_DSM_COG_10_", "_DEM.tif"


def tiles(role: str = "ground") -> list:
    """The DEM tiles' paths, in the configured order (sorted names when found in raw/)."""
    names = CFG["sources"]["copernicus"]["tiles"]
    if names:
        return [RAW / f"{PREFIX}{n}{SUFFIX}" for n in names]
    return sorted(RAW.glob(f"{PREFIX}*{SUFFIX}"))


def extent(role: str = "ground") -> tuple:
    """(west, south, east, north) in degrees covered by the tiles, from their names."""
    w = s = 999
    e = n = -999
    for p in tiles():
        m = re.search(r"([NS])(\d+)_\d+_([EW])(\d+)_\d+", p.name)
        lat = int(m[2]) * (1 if m[1] == "N" else -1)
        lon = int(m[4]) * (1 if m[3] == "E" else -1)
        w, s, e, n = min(w, lon), min(s, lat), max(e, lon + 1), max(n, lat + 1)
    return float(w), float(s), float(e), float(n)


def name(lat: int, lon: int) -> str:
    return f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00_{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00"


def wanted() -> list:
    """Tile names: the configured ones, else those under the ground area plus the backdrop's reach."""
    if CFG["sources"]["copernicus"]["tiles"]:
        return list(CFG["sources"]["copernicus"]["tiles"])
    from pyproj import Transformer
    from ..common import UTM, boundary
    pad = CFG["ground"]["margin"] + CFG["terrain"]["far_reach"]
    x0, y0, x1, y1 = boundary().total_bounds
    to = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    pts = [to.transform(x, y) for x in (x0 - pad, x1 + pad) for y in (y0 - pad, y1 + pad)]
    lo0, lo1 = math.floor(min(p[0] for p in pts)), math.floor(max(p[0] for p in pts))
    la0, la1 = math.floor(min(p[1] for p in pts)), math.floor(max(p[1] for p in pts))
    return [name(la, lo) for la in range(la0, la1 + 1) for lo in range(lo0, lo1 + 1)]


def fetch(role: str = "ground"):
    RAW.mkdir(parents=True, exist_ok=True)
    for n in wanted():
        f = RAW / f"{PREFIX}{n}{SUFFIX}"
        if f.exists():
            print(f"{f.name}: already here")
            continue
        url = f"{BUCKET}/{PREFIX}{n}_DEM/{PREFIX}{n}{SUFFIX}"
        r = requests.get(url, headers=HEADERS, timeout=600)
        if r.status_code == 404:          # no land in that square: no tile
            print(f"{f.name}: none (all sea)")
            continue
        r.raise_for_status()
        f.write_bytes(r.content)
        print(f"{f.name}: {len(r.content) / 1e6:.0f} MB")
