"""Source adapter "file": building footprints (with heights, when they have them) from a local vector file,
any format GDAL reads (GeoPackage, GeoJSON, shapefile, FlatGeobuf, GML...), configured in city.toml. One
module serves any number of sources: each is a table [sources.<name>] with adapter = "file", and runs as
stage 02_<name>. Official building layers are mostly published as downloads (Paris's APUR Emprise bâtie as
GeoJSON, IGN's BD TOPO as GeoPackage, cadastres as shapefiles); this reads them the same way.

[sources.<name>]:
  adapter       "file"
  path          the file, relative to the data folder's raw/ (or absolute); a list: several files, joined
  layer         the layer of a multi-layer file (a GeoPackage's "batiment"); "": the first
  crs           the file's CRS when it doesn't say (e.g. "EPSG:2154"); "": the file's own
  url           a direct download of `path`, fetched when the file is missing ("": it must be there)
  role          "primary" (default; authoritative footprints of every building, chosen before OSM, which fills
                what they lack), "blocks", "pieces" or "fill" (see sources/__init__.py)
  districts     the districts where it is the footprint source (04_buildings; default all): beyond them the
                next source is (OSM, or another primary's). Its heights still reach every footprint it
                covers (a height source everywhere)
  height        the roof height above the building's ground: a field, or an expression over the fields with
                numpy's where, maximum, minimum, isnan, abs (e.g. APUR's "where((b_igh == 'O') & (h_max >= 60),
                h_max, h_med)"), and `area` (the footprint's m², unless a field has that name: a mean height
                from a volume, London's "volume / area"); "": no heights
  mean          a mean roof height over the polygon, as `height` (a field or an expression; Carbon & Place's
                "volume / area"), where `height` is a maximum: 04_buildings' [buildings.spikes] tells a maximum
                that is a chimney or a neighbour's edge by it (column h_mean); "": none
  height_scale  its unit in metres (0.3048 for feet)
  keep          further fields copied into the table (lower-cased)
  rename        {field = "column"}: fields copied under another name, e.g. a ground altitude as
                "ground_elevation" (03_compare checks it against the DEM, a check of both)
  drop          {field = [values]}: features left out (demolished or planned buildings; structures that are
                modelled otherwise, such as the Eiffel Tower's parts)
  label         its name in reports ("": the source's name)
  lend          fields (of keep) also given to the other sources' footprints it covers (04_buildings: from its
                polygon covering most of each, where they have none of their own), e.g. BD TOPO's usage_1 on
                APUR's footprints for the building kinds
Features are read within the districts' bounding box, kept where they meet the districts, made valid and
flat (Z dropped: BD TOPO's roofs carry -1000 where unknown); heights of 0 or less are unknown (NaN).

Writes <name>_buildings.gpkg (WGS84) in the data folder, with h (m above ground) when it has heights,
source (the source's name) and the kept fields.
"""
import re
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from ..common import CFG, DATA, HEADERS, RAW, UTM, boundary, districts

DEFAULTS = {"path": "", "layer": "", "crs": "", "url": "", "role": "primary", "height": "", "mean": "", "height_scale": 1.0,
            "keep": [], "rename": {}, "drop": {}, "label": "", "lend": []}
FUNCS = {"where": np.where, "maximum": np.maximum, "minimum": np.minimum, "isnan": np.isnan, "abs": np.abs}


class FileSource:
    """A [sources.<name>] table with adapter = "file", with the attributes of a source module."""

    def __init__(self, name: str):
        self.name = name
        self.C = {**DEFAULTS, **CFG["sources"][name]}
        self.STAGE = f"02_{name}"
        self.ROLE = self.C["role"]
        self.HEIGHTS = bool(self.C["height"])
        self.LABEL = self.C["label"] or name
        self.OUT = DATA / f"{name}_buildings.gpkg"
        self.__name__ = f"{__name__}:{name}"

    def paths(self) -> list:
        p = self.C["path"]
        return [Path(q) if Path(q).is_absolute() else RAW / q for q in ([p] if isinstance(p, str) else p)]

    def load(self) -> gpd.GeoDataFrame:
        g = gpd.read_file(self.OUT).to_crs(UTM)
        g["geometry"] = g.geometry.make_valid()
        return g

    def fetch(self, path: Path):
        import requests
        if not self.C["url"]:
            raise FileNotFoundError(f"{path}: missing, and [sources.{self.name}] has no url to fetch it from")
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"{self.name}: downloading {self.C['url']}", flush=True)
        t0 = time.time()
        with requests.get(self.C["url"], headers=HEADERS, stream=True, timeout=600) as r:
            r.raise_for_status()
            tmp = path.with_suffix(path.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        tmp.rename(path)
        print(f"{path.name}: {path.stat().st_size / 1e6:.0f} MB in {time.time() - t0:.0f} s")

    def fields_used(self, fields: list) -> list:
        """The file's fields the settings name (keep, rename, drop, the height expression)."""
        want = set(self.C["keep"]) | set(self.C["rename"]) | set(self.C["drop"])
        for h in (self.C["height"], self.C["mean"]):
            if h:
                want |= {h} if h in fields else set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", h))
        return [f for f in fields if f in want]

    def heights(self, g: pd.DataFrame, key: str = "height") -> np.ndarray:
        h = self.C[key]
        if h in g:
            v = pd.to_numeric(g[h], errors="coerce").to_numpy(float)
        else:
            env = {c: g[c] for c in g.columns if c != "geometry"}
            if "area" not in env and re.search(r"\barea\b", h):
                env["area"] = g.geometry.to_crs(UTM).area      # m², for a mean height from a volume field
            v = np.asarray(eval(h, {"__builtins__": {}, "np": np, **FUNCS}, env), dtype=float)   # noqa: S307 (city.toml is trusted)
        v = v * self.C["height_scale"]
        return np.where(v > 0, v, np.nan)            # 0 or empty: not known

    def read(self, path: Path, bd: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        import pyogrio
        kw = {"layer": self.C["layer"]} if self.C["layer"] else {}
        info = pyogrio.read_info(path, **kw)
        crs = self.C["crs"] or info["crs"]
        bbox = tuple(bd.to_crs(crs).total_bounds)
        g = gpd.read_file(path, bbox=bbox, columns=self.fields_used(list(info["fields"])), **kw)
        if g.crs is None or self.C["crs"]:
            g = g.set_crs(crs, allow_override=True)
        print(f"{path.name}: {info['features']:,} features, {len(g):,} in the districts' box ({crs})")
        return g

    def main(self):
        bd = boundary()
        for p in self.paths():
            if not p.exists():
                self.fetch(p)
        g = pd.concat([self.read(p, bd) for p in self.paths()], ignore_index=True)
        g = gpd.GeoDataFrame(g, geometry="geometry")
        n0 = len(g)
        for field, values in self.C["drop"].items():
            out = g[field].isin(values)
            if out.any():
                print(f"drop {field} in {values}: {int(out.sum()):,}")
            g = g[~out]
        g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
        g["geometry"] = g.geometry.force_2d().make_valid()
        g = g[g.geom_type.isin(["Polygon", "MultiPolygon", "GeometryCollection"])]
        g["geometry"] = g.geometry.map(lambda s: s if s.geom_type != "GeometryCollection" else
                                       gpd.GeoSeries(list(s.geoms)).loc[lambda x: x.area > 0].union_all())
        gu = g.to_crs(UTM)
        g = g[gu.intersects(bd.geometry.iloc[0]).values & (gu.area > 0).values]
        cols = {k.lower(): g[k].values for k in self.C["keep"] if k in g}
        cols |= {v: g[k].values for k, v in self.C["rename"].items() if k in g}
        out = gpd.GeoDataFrame(cols, geometry=g.geometry.values, crs=g.crs).to_crs("EPSG:4326")
        if self.HEIGHTS:
            out["h"] = self.heights(g)
            if self.C["mean"]:
                out["h_mean"] = self.heights(g, "mean")
        out["source"] = self.name
        self.OUT.parent.mkdir(parents=True, exist_ok=True)
        out.to_file(self.OUT)
        L = [f"{self.LABEL}: {n0:,} read, {len(out):,} in the districts; "
             f"with height: {int(out['h'].notna().sum()) if self.HEIGHTS else 0:,} → {self.OUT.name}"]
        # per district, by representative point (a footprint on a boundary counts once)
        dd = districts()
        pts = gpd.GeoDataFrame(geometry=out.to_crs(UTM).geometry.representative_point(), crs=UTM)
        j = gpd.sjoin(pts, dd[["name", "geometry"]], predicate="within", how="left")
        j = j[~j.index.duplicated()]
        counts = j["name"].value_counts()
        L += [f"  {n}: {counts.get(n, 0):,}" for n in dd.name]
        if self.HEIGHTS:
            L.append(out["h"].describe().round(1).to_string())
        print("\n".join(L))


def instance(name: str) -> FileSource:
    return FileSource(name)
