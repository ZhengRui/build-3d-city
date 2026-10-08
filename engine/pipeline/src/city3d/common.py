"""Paths and helpers shared by the stages: the city's folders, projection and districts (city.toml, see
config.py), fetching from Overpass, and the scene's ground (Terrain)."""
import hashlib
import json
import os
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

from . import config

CFG = config.get()
CITY = Path(CFG["city_dir"])                                  # demos/<city>: city.toml, data/, checks/, web/
DATA = Path(os.path.normpath(CITY / CFG["paths"]["data"]))    # demos/data/<city> (git-ignored)
RAW = DATA / "raw"
CHECKS = CITY / CFG["paths"]["checks"]
CHECKS.mkdir(parents=True, exist_ok=True)
WEB = CITY / CFG["paths"]["web"]
TERRAIN = DATA / "terrain.npz"        # the ground's TIN and the backdrop (05a_terrain)
UTM_EPSG = int(CFG["utm_epsg"])
UTM = f"EPSG:{UTM_EPSG}"              # metres
LEVEL_H = CFG["level_h"]              # metres per storey for OSM building:levels
DISTRICTS = CFG["districts"]          # districts in the scene: name -> OSM relation id, or {relation, clip}
OVERPASS = CFG["overpass"]
HEADERS = {"User-Agent": CFG["user_agent"]}
UNDERGROUND_DROP = bool(CFG.get("osm", {}).get("underground_drop", False))   # [osm] underground_drop
MIN_HEIGHT_TAGS = bool(CFG.get("osm", {}).get("min_height", False))          # [osm] min_height
# [osm] min_height = "decks": only deck-like outlines keep their min_height (04_buildings deck_rule())
MIN_HEIGHT_DECKS = CFG.get("osm", {}).get("min_height", False) == "decks"


def generator(stage: str) -> str:
    """The glb 'generator' string of a stage."""
    return f"{CFG['generator']} {stage}.py"


def link_web(folder: str):
    """web/<folder> -> the data folder of that name (a relative link, like web/tiles), so web/ alone can be
    served."""
    link = WEB / folder
    if not link.exists() and not link.is_symlink():
        WEB.mkdir(parents=True, exist_ok=True)
        link.symlink_to(os.path.relpath(DATA / folder, WEB))


def origin() -> tuple:
    """The scene origin: the centre of the districts' bounding box (UTM)."""
    x0, y0, x1, y1 = boundary().total_bounds
    return (x0 + x1) / 2, (y0 + y1) / 2


def overpass(query: str, timeout: int = 900) -> dict:
    """Try each public Overpass mirror in turn; they are often busy (429/504).

    With $CITY3D_OVERPASS_CACHE set (city3d --overpass-cache DIR), each answer is recorded there under its
    query and replayed on later runs, so a refactor can be checked against the very same OSM data."""
    cache = os.environ.get("CITY3D_OVERPASS_CACHE")
    if not cache:
        return _fetch(query, timeout)
    f = Path(cache) / (hashlib.sha1(" ".join(query.split()).encode()).hexdigest()[:16] + ".json")
    if f.exists():
        return json.loads(f.read_text())
    res = _fetch(query, timeout)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(res))
    return res


def _fetch(query: str, timeout: int) -> dict:
    errors = []
    for url in OVERPASS * 2:
        try:
            r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            res = r.json()
            # a query that runs out of time or memory still answers 200, with a remark and partial data
            remark = res.get("remark", "")
            if "error" in remark.lower() or "timed out" in remark.lower():
                raise requests.RequestException(f"incomplete answer: {remark[:200]}")
            return res
        except requests.RequestException as e:
            errors.append(f"{url}: {e}")
            time.sleep(10)
    raise RuntimeError("all Overpass mirrors failed:\n" + "\n".join(errors))


def element_geoms(res: dict):
    """Yield (tags, geometry) for ways and multipolygon relations returned with `out geom`."""
    for e in res["elements"]:
        t = e.get("tags", {})
        if e["type"] == "way":
            pts = [(p["lon"], p["lat"]) for p in e["geometry"]]
            if len(pts) >= 4 and pts[0] == pts[-1]:
                yield t, Polygon(pts)
            elif len(pts) >= 2:
                yield t, LineString(pts)
        elif e["type"] == "relation":
            outer = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                     for m in e["members"] if m.get("role") == "outer" and "geometry" in m]
            inner = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                     for m in e["members"] if m.get("role") == "inner" and "geometry" in m]
            if not outer:
                continue
            g = unary_union(list(polygonize(unary_union(outer))))
            if inner:
                g = g.difference(unary_union(list(polygonize(unary_union(inner)))))
            yield t, g


def load_osm(underground: bool = False) -> gpd.GeoDataFrame:
    """OSM buildings above ground. Metro stations are often mapped as building=train_station outlines tagged
    location=underground / layer<0 (most of Shenzhen's are); kept, they would win over the towers standing on
    top of them. underground=True keeps them all (04_buildings' [buildings] surface_layers sorts them)."""
    osm = gpd.read_file(DATA / "osm_buildings.gpkg").to_crs(UTM)
    layer = pd.to_numeric(osm["layer"], errors="coerce").fillna(0)
    if not underground:
        osm = osm[(osm["location"] != "underground") & (layer >= 0)]
    if UNDERGROUND_DROP:                # [osm] underground_drop: tagged underground / indoor / a level below 0, always
        osm = osm[~underground_mask(osm)]
    osm = osm.copy()
    osm["h_tag"] = osm["height"].map(height_m)
    osm["h_levels"] = osm["levels"].map(height_m) * LEVEL_H
    osm["h"] = osm["h_tag"].fillna(osm["h_levels"])
    if MIN_HEIGHT_TAGS and "min_height" in osm:     # [osm] min_height: where a building starts above the ground (m)
        osm["min_h_tag"] = osm["min_height"].map(height_m).fillna(osm["min_level"].map(height_m) * LEVEL_H)
    osm["geometry"] = osm.geometry.make_valid()
    return osm


def level_below_ground(v) -> bool:
    """An OSM `level` tag ("-1", "-2;-1") entirely under 0; anything unreadable ("B1", "-1-0", empty) is not."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return False
    try:
        vals = [float(p) for p in str(v).split(";") if p.strip()]
    except ValueError:
        return False
    return bool(vals) and max(vals) < 0


def underground_mask(o: pd.DataFrame) -> pd.Series:
    """[osm] underground_drop: the OSM outlines (buildings or parts) tagged underground=yes, location=underground or
    indoor, or with a level entirely under 0 (a missing column counts as untagged)."""
    no = pd.Series(False, index=o.index)
    ug = o["underground"].astype(str).str.lower().isin(["yes", "true", "1"]) if "underground" in o else no
    loc = o["location"].isin(["underground", "indoor"]) if "location" in o else no
    lev = o["level"].map(level_below_ground).astype(bool) if "level" in o else no
    return ug | loc | lev


def height_m(v) -> float:
    """An OSM height (or levels) tag as a number: metres unless in feet ("103'", "103 ft", "12'6\""); of
    several values ("37;35") the largest; NaN when there is none."""
    import re
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    out = []
    for part in str(v).replace(",", ".").split(";"):
        t = part.strip().lower()
        m = re.match(r"^([\d.]+)\s*(?:'|ft|feet)\s*(?:([\d.]+)\s*(?:\"|in))?$", t)
        if m:
            out.append(float(m[1]) * 0.3048 + (float(m[2]) * 0.0254 if m[2] else 0.0))
            continue
        m = re.match(r"^([\d.]+)", t)
        if m:
            try:
                out.append(float(m[1]))
            except ValueError:
                pass
    return max(out) if out else np.nan


def districts() -> gpd.GeoDataFrame:
    """One row per district in DISTRICTS."""
    return gpd.read_file(DATA / "boundary.gpkg").to_crs(UTM)


def boundary() -> gpd.GeoDataFrame:
    """The whole scene area: the union of all districts, as a single row."""
    d = districts()
    return gpd.GeoDataFrame({"name": ["+".join(d.name)]}, geometry=[d.union_all()], crs=UTM)


class Terrain:
    """The scene's ground (05a_terrain): a TIN, linear on each triangle, 0 beyond it. Positions are scene
    coordinates (x east, z south, metres from 06_tiles' origin) unless a name says utm.

    Everything that stands on the ground reads it here, so buildings, roads, markings, shores, trees and cars
    agree with the ground layers, which drape() clips to its triangles."""

    def __init__(self):
        import matplotlib.tri as mtri
        d = np.load(TERRAIN)
        self.origin = tuple(float(v) for v in d["origin"])
        self.cell = cell = float(d["cell"])
        self.xz = np.stack([d["x0"] + d["ij"][:, 0] * cell, d["z0"] + d["ij"][:, 1] * cell], 1).astype(np.float64)
        self.y = d["y"].astype(np.float64)
        self.tri = d["tri"].astype(np.int64)
        self.backdrop = {k: d[k] for k in ("back_xyz", "back_tri", "back_rgb", "back_h") if k in d}
        self._mtri = mtri.Triangulation(self.xz[:, 0], self.xz[:, 1], self.tri)
        self._interp = mtri.LinearTriInterpolator(self._mtri, self.y)
        self._finder = self._mtri.get_trifinder()
        # smooth shading: area-weighted vertex normals (scene x, y, z)
        p = np.column_stack([self.xz[:, 0], self.y, self.xz[:, 1]])
        n = np.cross(p[self.tri[:, 2]] - p[self.tri[:, 0]], p[self.tri[:, 1]] - p[self.tri[:, 0]])
        n *= np.sign(n[:, 1:2] + 1e-12)
        vn = np.zeros_like(p)
        for k in range(3):
            np.add.at(vn, self.tri[:, k], n)
        self.normal = vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
        tp = self.xz[self.tri]
        self.polys = shapely.polygons(np.concatenate([tp, tp[:, :1]], 1))
        self.tree = shapely.STRtree(self.polys)
        ty = self.y[self.tri]
        self.level = np.where(ty.max(1) == ty.min(1), ty[:, 0], np.nan)   # height of level triangles

    def to_scene(self, e, n):
        return np.asarray(e, np.float64) - self.origin[0], self.origin[1] - np.asarray(n, np.float64)

    def height(self, x, z):
        return np.asarray(self._interp(np.asarray(x, np.float64), np.asarray(z, np.float64)).filled(0.0))

    def height_utm(self, e, n):
        return self.height(*self.to_scene(e, n))

    def plane(self, t, x, z):
        """Heights and normals at (x, z) on TIN triangles t (arrays of the same length)."""
        v = self.tri[t]
        a, b, c = self.xz[v[:, 0]], self.xz[v[:, 1]], self.xz[v[:, 2]]
        det = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
        u = ((x - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (z - a[:, 1])) / det
        w = ((b[:, 0] - a[:, 0]) * (z - a[:, 1]) - (x - a[:, 0]) * (b[:, 1] - a[:, 1])) / det
        bary = np.stack([1 - u - w, u, w], 1)
        y = (bary * self.y[v]).sum(1)
        nrm = (bary[:, :, None] * self.normal[v]).sum(1)
        return y, nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)

    def bases(self, geoms_utm, step: float = 4.0) -> np.ndarray:
        """Per footprint (UTM polygons), the lowest ground under its outline (sampled every `step` m)."""
        g = shapely.segmentize(np.asarray(geoms_utm), step)
        xy, owner = shapely.get_coordinates(g, return_index=True)
        h = self.height(*self.to_scene(xy[:, 0], xy[:, 1]))
        out = np.full(len(g), np.inf)
        np.minimum.at(out, owner, h)
        return np.where(np.isfinite(out), out, 0.0)

    def drape(self, poly, max_coords: int = 300) -> list:
        """A polygon (scene x, z) laid on the ground: [(xz Nx2, y N, normals Nx3, triangles Mx3)], one entry
        per piece. Where the ground under it is level (the plain at 0, a lake) it stays whole; elsewhere
        it is cut along the TIN's triangles, so every piece lies in one plane of the ground."""
        out = []
        if not poly.is_valid:
            poly = shapely.make_valid(poly)
        parts = [q for p in _polygons(poly) for q in _quarter(p, max_coords)]
        for part in (q for p in parts for q in (_polygons(shapely.make_valid(p)) if not p.is_valid else [p])):
            cand = self.tree.query(part)
            if not len(cand):
                out += _flat_pieces(part, 0.0)
                continue
            lv = self.level[cand]
            if np.isfinite(lv).all() and (lv == lv[0]).all():
                out += _flat_pieces(part, float(lv[0]))
                continue
            pieces = shapely.intersection(part, self.polys[cand])
            for t, piece in zip(cand, pieces):
                for p in _polygons(piece):
                    if p.area < 1e-3:
                        continue
                    v2, tri = _earcut(p)
                    if not len(tri):
                        continue
                    y, nrm = self.plane(np.full(len(v2), t), v2[:, 0], v2[:, 1])
                    out.append((v2, y, nrm, tri))
        return out

    def drape_triangles(self, xz, tri, tol: float = 0.0):
        """Triangles (scene x, z; vertex array xz, index array tri Mx3) cut along the TIN wherever the
        ground under one is not level, or with `tol`, not flat enough that a plane through the ground at its
        corners stays within tol of it (checked at the edges' midpoints and the centre). Returns (xz Nx2,
        source triangle per vertex, barycentric weights Nx3 in that source triangle, ground heights N,
        ground normals Nx3, triangles Kx3), so callers can interpolate their own vertex attributes."""
        xz = np.asarray(xz, np.float64)
        tri = np.asarray(tri, np.int64)
        tp = xz[tri]
        polys = shapely.polygons(np.concatenate([tp, tp[:, :1]], 1))
        src, cand = self.tree.query(polys)
        # triangles over level ground stay whole
        lv = self.level[cand]
        lo = np.full(len(tri), np.inf)
        hi = np.full(len(tri), -np.inf)
        np.minimum.at(lo, src, np.where(np.isfinite(lv), lv, -np.inf))
        np.maximum.at(hi, src, np.where(np.isfinite(lv), lv, np.inf))
        whole = (lo == hi) | ~np.isin(np.arange(len(tri)), src)
        level = np.where(np.isfinite(lo) & whole, lo, 0.0)
        pos, own, bary, ys, nrms, idx, n = [], [], [], [], [], [], 0
        w = np.flatnonzero(whole)
        if len(w):
            k = len(w)
            pos.append(tp[w].reshape(-1, 2))
            own.append(np.repeat(w, 3))
            bary.append(np.tile(np.eye(3), (k, 1)))
            ys.append(np.repeat(level[w], 3))
            nrms.append(np.tile([0.0, 1.0, 0.0], (3 * k, 1)))
            idx.append(np.arange(3 * k).reshape(-1, 3))
            n = 3 * k
        if tol > 0:
            # nearly flat under a triangle: it stays whole, its corners on the ground
            f = np.flatnonzero(~whole)
            corners = tp[f].reshape(-1, 2)
            yc = self.height(corners[:, 0], corners[:, 1]).reshape(-1, 3)
            probe = np.concatenate([(tp[f] + np.roll(tp[f], -1, axis=1)) / 2, tp[f].mean(1, keepdims=True)], 1)
            yp = self.height(probe[..., 0].ravel(), probe[..., 1].ravel()).reshape(-1, 4)
            lin = np.concatenate([(yc + np.roll(yc, -1, axis=1)) / 2, yc.mean(1, keepdims=True)], 1)
            ok = np.abs(yp - lin).max(1) <= tol
            g = f[ok]
            if len(g):
                c = tp[g].reshape(-1, 2)
                t = self._finder(c[:, 0], c[:, 1])
                y, nrm = self.plane(np.maximum(t, 0), c[:, 0], c[:, 1])
                nrm[t < 0] = [0.0, 1.0, 0.0]
                pos.append(c)
                own.append(np.repeat(g, 3))
                bary.append(np.tile(np.eye(3), (len(g), 1)))
                ys.append(np.where(t < 0, 0.0, y))
                nrms.append(nrm)
                idx.append(n + np.arange(3 * len(g)).reshape(-1, 3))
                n += 3 * len(g)
                whole[g] = True
        keep = ~whole[src]
        src, cand = src[keep], cand[keep]
        pieces = shapely.intersection(polys[src], self.polys[cand])
        for s, t, piece in zip(src, cand, pieces):
            for p in _polygons(piece):
                c = np.asarray(p.exterior.coords)[:-1]
                if len(c) < 3 or p.area < 1e-4:
                    continue
                m = len(c)
                a, b, cc = tp[s]
                det = (b[0] - a[0]) * (cc[1] - a[1]) - (cc[0] - a[0]) * (b[1] - a[1])
                u = ((c[:, 0] - a[0]) * (cc[1] - a[1]) - (cc[0] - a[0]) * (c[:, 1] - a[1])) / det
                v = ((b[0] - a[0]) * (c[:, 1] - a[1]) - (c[:, 0] - a[0]) * (b[1] - a[1])) / det
                y, nrm = self.plane(np.full(m, t), c[:, 0], c[:, 1])
                pos.append(c)
                own.append(np.full(m, s))
                bary.append(np.stack([1 - u - v, u, v], 1))
                ys.append(y)
                nrms.append(nrm)
                idx.append(n + np.stack([np.zeros(m - 2, int), np.arange(1, m - 1), np.arange(2, m)], 1))  # convex: a fan
                n += m
        if not pos:
            return None
        return (np.concatenate(pos), np.concatenate(own), np.concatenate(bary), np.concatenate(ys),
                np.concatenate(nrms), np.concatenate(idx))


def weld(m: dict, keys=None) -> dict:
    """Vertices equal in every attribute (positions to a millimetre, the rest to 1e-4) merged into one: the
    triangles drape_triangles cuts or keeps whole come with vertices of their own."""
    keys = keys or [k for k in m if k != "idx"]
    cols = [np.round(np.asarray(m[k], np.float64).reshape(len(m[k]), -1) * (1000 if k == "pos" else 10000))
            for k in keys]
    rows = np.ascontiguousarray(np.concatenate(cols, 1).astype(np.int64))
    _, first, inv = np.unique(rows, axis=0, return_index=True, return_inverse=True)
    t = inv.reshape(-1)[np.asarray(m["idx"])].reshape(-1, 3)
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]     # slivers that collapsed
    return {**{k: v[first] for k, v in m.items() if k != "idx"}, "idx": t}


def _polygons(g):
    return [g] if g.geom_type == "Polygon" else [q for p in getattr(g, "geoms", []) for q in _polygons(p)]


def _quarter(poly, max_coords):
    """A polygon cut into quarters until each piece has at most max_coords points (or is under 100 m)."""
    x0, y0, x1, y1 = poly.bounds
    if shapely.get_num_coordinates(poly) <= max_coords or max(x1 - x0, y1 - y0) < 100:
        return _polygons(poly)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    out = []
    for r in ((x0, y0, mx, my), (mx, y0, x1, my), (x0, my, mx, y1), (mx, my, x1, y1)):
        q = shapely.clip_by_rect(poly, *r)
        if not q.is_empty:
            for p in _polygons(q):
                out += _quarter(p, max_coords)
    return out


def _earcut(poly):
    import mapbox_earcut as earcut
    rings = [np.asarray(poly.exterior.coords)[:-1]] + [np.asarray(r.coords)[:-1] for r in poly.interiors]
    rings = [r for r in rings if len(r) >= 3]
    if not rings:
        return np.zeros((0, 2)), np.zeros((0, 3), np.int64)
    verts = np.concatenate(rings)
    ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
    return verts, earcut.triangulate_float64(verts, ends).reshape(-1, 3).astype(np.int64)


def _flat_pieces(poly, y):
    v2, tri = _earcut(poly)
    if not len(tri):
        return []
    return [(v2, np.full(len(v2), y), np.tile([0.0, 1.0, 0.0], (len(v2), 1)), tri)]


def best_match(a: gpd.GeoDataFrame, b: gpd.GeoDataFrame, cols=("h",)) -> pd.DataFrame:
    """For each footprint in a (by index label), the b footprint with the largest overlap.

    Returns ia, ib (index labels), inter (m²), iou, and cols from a/b suffixed _a/_b.
    """
    cols = list(cols)
    aa = a[["geometry", *cols]].reset_index(names="ia")
    bb = b[["geometry", *cols]].reset_index(names="ib")
    ov = gpd.overlay(aa, bb, how="intersection", keep_geom_type=True)
    ov["inter"] = ov.area
    ov = ov.sort_values("inter", ascending=False).drop_duplicates("ia")
    area_a = aa.set_index("ia").area
    area_b = bb.set_index("ib").area
    ov["area_a"] = area_a.loc[ov.ia].values
    ov["area_b"] = area_b.loc[ov.ib].values
    ov["iou"] = ov["inter"] / (ov["area_a"] + ov["area_b"] - ov["inter"])
    ren = {f"{c}_1": f"{c}_a" for c in cols} | {f"{c}_2": f"{c}_b" for c in cols}
    return pd.DataFrame(ov.drop(columns="geometry").rename(columns=ren))
