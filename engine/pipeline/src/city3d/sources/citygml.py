"""Source adapter "citygml": building footprints with heights and roof facts from CityGML LoD2 tiles (Berlin's
LoD2 from the gdi.berlin.de ATOM feed; any German state's AdV LoD2, PLATEAU-style CityGML 1.0/2.0 with the same
building module), configured in city.toml like the "file" adapter, whose keys it takes (role, districts, height,
keep, rename, drop, label, lend: sources/file.py). One module serves any number of sources: each is a table
[sources.<name>] with adapter = "citygml", stage 02_<name>.

[sources.<name>] besides file's keys:
  adapter   "citygml"
  path      tiles, relative to raw/ (or absolute): glob patterns or a list of them; a .zip is read member by member
            (its .gml / .xml files, in place, never unpacked to disk), a .gml / .xml directly
  crs       the tiles' horizontal CRS (required unless their srsName is an EPSG URN; Berlin's
            "urn:adv:crs:ETRS89_UTM33*DE_DHHN2016_NH" is EPSG:25833 plus NHN heights; PLATEAU: "EPSG:6668")
  height    default "measuredHeight"
  flavour   "" (default: CityGML 1.0/2.0 LoD2 as Berlin's, coordinates x, y, z) or "plateau" (below)

Each tile is parsed on its own (xml.etree iterparse, one cityObjectMember at a time, cleared after use), so the
memory is that of one building plus the rows so far, whatever the tile size. A row per solid: a Building
without parts, or each of a Building's BuildingParts (a parent with parts has no geometry of its own; its
attributes reach its parts where they have none). Fields:
  gml_id, parent_id (the Building of a part; "" for a Building), part (bool), function, roofType,
  measuredHeight (m, as the file has it), name (gml:name, rare), ground_z (the lowest GroundSurface z),
  roof_top_z, eave_z (highest and lowest RoofSurface z), roof_area (m² of roof polygons, sloped),
  n_roof, n_wall (surface polygon counts), and every gen:stringAttribute / intAttribute / doubleAttribute
  (Berlin: DatenquelleDachhoehe, DatenquelleBodenhoehe, DatenquelleLage, Grundrissaktualitaet ...).
The footprint is the union of the solid's GroundSurface polygons (2D); a solid without one gets the 2D union
of its roof polygons (counted in the report). ClosureSurfaces (the cut faces between parts) are ignored.

The 3D surfaces themselves (roofs and walls for the viewer) are not kept here: M1 needs footprints, heights and
roof facts; a roof mesh stage reads the tiles again.

Every flavour: a .gml.gz / .xml.gz tile is read through gzip in place, and each CityModel member is dropped once
parsed, the CityModel-level app:appearanceMember block too, child by child while it streams (PLATEAU files open
with 50-60 MB of texture and material references before the first building: a 166 MB mesh peaked at 0.41 GB
without this, 0.13 GB with, 0.09 GB of it the imports).

flavour = "plateau" (opt-in; "" is the default and reads CityGML as Berlin's code always did): Japan's MLIT
PLATEAU CityGML 2.0 with the i-UR (uro:) extension, FY2023-FY2025 specs.
  - Coordinates are EPSG:6697 (JGD2011 lat, lon + JGD2011 height), posList in lat, lon, h order: each solid's
    rings are projected straight to the city's UTM with pyproj in the CRS's own axis order (crs defaults to
    "EPSG:6668", the 2D JGD2011; a compound CRS is reduced to its horizontal part), so roof areas are in m².
  - Only LoD2 thematic surfaces count (bldg:lod2MultiSurface under Ground/Roof/WallSurface): LoD3 buildings carry
    lod3MultiSurface twins of the same surfaces, which would double the roof area.
  - A solid without LoD2 surfaces (LOD1-only: a third of central Tokyo's buildings) gets its footprint from
    bldg:lod0FootPrint, else bldg:lod0RoofEdge, else the bottom ring(s) of bldg:lod1Solid (fp_from says which),
    ground_z from the lod1Solid's lowest z, roof_top_z = eave_z its highest (a flat block), roof_area NaN.
    ground_z of an LoD2 solid without a GroundSurface falls back to the lod1Solid too.
  - Fields besides the above: lod (2: LoD2 surfaces, 1: lod1Solid, 0: lod0 only), usage, class,
    storeysAboveGround, storeysBelowGround, and from uro: buildingRoofEdgeArea, detailedUsage,
    buildingStructureType, fireproofStructureType, surveyYear (uro:buildingDetailAttribute), lod1HeightType,
    lodType (uro:bldgDataQualityAttribute), buildingID (uro:buildingIDAttribute); PLATEAU's "no value" -9999 /
    9999 in measuredHeight, storeys and buildingRoofEdgeArea is dropped (NaN). Coded fields get an English
    <field>_name column (usage_name, class_name, roofType_name, detailedUsage_name, buildingStructureType_name,
    fireproofStructureType_name, lod1HeightType_name) from the standard codelists embedded in
    plateau_codelists.json.
  - Buildings are deduplicated by gml:id across the source's files (a mesh on a ward border is published by
    every ward it touches, the same buildings; two adjacent FY2025 meshes shared no gml:id): the first file read
    (in path order) keeps it, and a repeat is skipped before its geometry is read.
  - In a .zip (a whole ward's dataset), only members under udx/bldg/ ending .gml are read.

roof_split = {} (opt-in, off by default; any flavour; Tokyo M2): a LoD2 solid whose roof stands at several levels
(a tower on its podium in one Building: PLATEAU's Roppongi Hills, 22,800 m² from one 235 m top) becomes one row per
roof level, so a podium is not drawn at its tower's height. Keys (defaults when the table is given):
  min_area 300   m²: smaller footprints stay whole
  tol 3.0, rel_tol 0.08
                 roof polygons (each at its highest z) join the level above them while within max(tol,
                 rel_tol x its height over the ground) of that level's top
  min_part 40    m²: a smaller level (a plant room, a crown's tip, a gap between roof polygons) goes to the
                 neighbour it shares the longest edge with, at that neighbour's height
  min_width 2.0  m: thinner slivers are cut off and go the same way
  cover 0.8      the roof polygons must cover this share of the footprint (seen from above), else no split
  max_parts 12   at most this many levels (the smallest merged first)
Each level is the footprint under its roof polygons (minus the higher levels): rows with gml_id "<id>#r<k>"
(k = 0 the highest), parent_id the Building's id, part true, roof_level k, roof_levels the count, roof_top_z /
eave_z / roof_area / n_roof of its own polygons; ground_z, measuredHeight and the attributes stay the building's
(so a level's height is roof_top_z - ground_z, not measuredHeight). Solids not split get roof_level NaN.
"""
import glob
import gzip
import json
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Polygon

from pyproj import CRS, Transformer

from .file import FileSource, DEFAULTS as FILE_DEFAULTS
from ..common import CFG, RAW, UTM

DEFAULTS = {**FILE_DEFAULTS, "height": "measuredHeight", "flavour": "", "roof_split": {}}
SPLIT_DEFAULTS = {"min_area": 300.0, "tol": 3.0, "rel_tol": 0.08, "min_part": 40.0, "min_width": 2.0, "cover": 0.8,
                  "max_parts": 12}
FLAVOURS = ("", "plateau")
GML = "{http://www.opengis.net/gml}"
XLINK = "{http://www.w3.org/1999/xlink}"
SOLID = ("Building", "BuildingPart")
FIELDS = ("function", "roofType", "measuredHeight", "class", "usage", "yearOfConstruction", "storeysAboveGround")
# PLATEAU (flavour "plateau"): more bldg: fields, the uro: groups read and their fields kept, the "no value" sentinels
P_FIELDS = FIELDS + ("storeysBelowGround",)
URO_GROUPS = ("buildingDetailAttribute", "bldgDataQualityAttribute", "buildingIDAttribute")
URO_FIELDS = ("buildingRoofEdgeArea", "detailedUsage", "buildingStructureType", "fireproofStructureType", "surveyYear",
              "lod1HeightType", "lodType", "buildingID")
P_NUMERIC = ("measuredHeight", "storeysAboveGround", "storeysBelowGround", "buildingRoofEdgeArea")
P_NONE = ("-9999", "9999", "-9999.0", "9999.0")
CODELISTS = Path(__file__).with_name("plateau_codelists.json")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def ring(el) -> np.ndarray:
    """A gml:LinearRing's points (n, 3) from posList or pos elements."""
    pl = el.find(f"{GML}posList")
    if pl is not None and pl.text:
        dim = int(pl.get("srsDimension", "3"))
        return np.array(pl.text.split(), dtype=float).reshape(-1, dim)
    pts = [p.text.split() for p in el.iter(f"{GML}pos")]
    if pts:
        return np.array(pts, dtype=float)
    pts = [[c.text for c in p] for p in el.iter(f"{GML}coord")]     # GML 2 style X/Y/Z
    return np.array(pts, dtype=float) if pts else np.zeros((0, 3))


def polygons(surface) -> list:
    """(exterior (n,3), [interiors]) of every gml:Polygon under a thematic surface."""
    out = []
    for poly in surface.iter(f"{GML}Polygon"):
        ext = poly.find(f"{GML}exterior")
        if ext is None:
            continue
        lr = ext.find(f"{GML}LinearRing")
        if lr is None:
            continue
        holes = [ring(i.find(f"{GML}LinearRing")) for i in poly.findall(f"{GML}interior")
                 if i.find(f"{GML}LinearRing") is not None]
        out.append((ring(lr), holes))
    return out


def area3d(p: np.ndarray) -> float:
    """Area of a planar 3D ring (Newell's method)."""
    if len(p) < 3:
        return 0.0
    q = np.roll(p, -1, axis=0)
    n = np.array([np.sum((p[:, 1] - q[:, 1]) * (p[:, 2] + q[:, 2])),
                  np.sum((p[:, 2] - q[:, 2]) * (p[:, 0] + q[:, 0])),
                  np.sum((p[:, 0] - q[:, 0]) * (p[:, 1] + q[:, 1]))])
    return float(np.linalg.norm(n) / 2)


def flat(polys: list):
    """The 2D union of polygons given as (exterior, holes)."""
    geoms = []
    for ext, holes in polys:
        if len(ext) < 4:
            continue
        g = Polygon(ext[:, :2], [h[:, :2] for h in holes if len(h) >= 4])
        if not g.is_valid:
            g = shapely.make_valid(g)
        if g.area > 0:
            geoms.append(g)
    if not geoms:
        return None
    u = shapely.union_all(geoms)
    return u if u.area > 0 else None


def attrs(el, plateau: bool = False) -> dict:
    """An object's own attributes (direct children only: a Building's are not its parts')."""
    a = {}
    fields = P_FIELDS if plateau else FIELDS
    for c in el:
        t = local(c.tag)
        if t in fields and c.text is not None:
            a[t] = c.text.strip()
        elif plateau and t in URO_GROUPS:
            for d in c.iter():
                u = local(d.tag)
                if u in URO_FIELDS and d.text and d.text.strip() and u not in a:
                    a[u] = d.text.strip()
        elif t == "name" and c.tag.startswith(GML) and c.text:
            a["name"] = c.text.strip()
        elif t in ("stringAttribute", "intAttribute", "doubleAttribute", "dateAttribute"):
            v = c.find("{*}value")
            if c.get("name") and v is not None and v.text is not None:
                a[c.get("name")] = v.text.strip()
    if plateau:
        for k in P_NUMERIC:
            if a.get(k) in P_NONE:
                del a[k]
    return a


class Plateau:
    """flavour = "plateau": rings projected from the tiles' lat/lon CRS (authority axis order) to the city's UTM."""

    def __init__(self, crs: str):
        c = CRS(crs)
        if c.is_compound:
            c = c.sub_crs_list[0]
        self.tr = Transformer.from_crs(c, UTM)
        self.seen = set()       # Building gml:ids read so far (dedupe across meshes and wards)
        self.dup = 0            # Buildings skipped as already read

    def project(self, polys: list) -> list:
        """(exterior, holes) rings in lat, lon, h -> UTM x, y, h: one pyproj call per solid."""
        rings = [r for e, hs in polys for r in (e, *hs)]
        if not rings:
            return polys
        p = np.concatenate(rings)
        x, y = self.tr.transform(p[:, 0], p[:, 1])
        q = np.column_stack([x, y, p[:, 2:]])
        out, i = [], 0
        for e, hs in polys:
            ring_n = [len(r) for r in (e, *hs)]
            rr = []
            for n in ring_n:
                rr.append(q[i:i + n])
                i += n
            out.append((rr[0], rr[1:]))
        return out


def surface_polygons(s, pl) -> list:
    """A thematic surface's polygons; PLATEAU: its LoD2 geometry only (LoD3 buildings repeat it as lod3MultiSurface)."""
    if pl is None:
        return polygons(s)
    return [p for c in s if local(c.tag) == "lod2MultiSurface" for p in polygons(c)]


def solid_row(el, gid: str, parent: str, inherited: dict, pl: Plateau | None = None) -> dict:
    """One solid's row: attributes, footprint and roof facts."""
    a = {**inherited, **attrs(el, pl is not None)}
    ground, roof, nwall = [], [], 0
    for b in el.findall("{*}boundedBy"):
        for s in b:
            t = local(s.tag)
            if t == "GroundSurface":
                ground += surface_polygons(s, pl)
            elif t == "RoofSurface":
                roof += surface_polygons(s, pl)
            elif t == "WallSurface":
                nwall += len(surface_polygons(s, pl))
    if pl is not None:
        ground, roof = pl.project(ground), pl.project(roof)
    fp = flat(ground)
    row = {**a, "gml_id": gid, "parent_id": parent, "part": bool(parent), "n_roof": len(roof), "n_wall": nwall,
           "fp_from": "ground"}
    if fp is None:
        fp, row["fp_from"] = flat(roof), "roof"
    gz = [p[:, 2].min() for p, _ in ground if len(p) and p.shape[1] > 2]
    rz = np.concatenate([p[:, 2] for p, _ in roof if len(p) and p.shape[1] > 2]) if roof else np.zeros(0)
    row["ground_z"] = float(min(gz)) if gz else np.nan
    row["roof_top_z"] = float(rz.max()) if len(rz) else np.nan
    row["eave_z"] = float(rz.min()) if len(rz) else np.nan
    row["roof_area"] = float(sum(area3d(p) for p, _ in roof))
    if pl is not None:
        plateau_lod1(el, row, fp is None, bool(ground or roof), pl)
        fp = row.pop("_fp", fp)
    row["geometry"] = fp
    row["_roof"] = roof
    return row


def _poly(g):
    """g's polygonal part (a union or difference can leave lines and points in a GeometryCollection)."""
    if g.geom_type == "GeometryCollection":
        g = shapely.union_all([p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")])
    return g


def _clean(g, w: float):
    """g's polygonal part without slivers thinner than w (an opening by w / 2)."""
    if g is None or g.is_empty:
        return None
    g = _poly(shapely.make_valid(g))
    if w > 0 and not g.is_empty:
        g = _poly(g.buffer(-w / 2, join_style=2).buffer(w / 2, join_style=2).intersection(g))
    return None if g.is_empty or g.area <= 0 else g


def roof_levels(roof: list, fp, ground_z: float, C: dict) -> list | None:
    """[roof_split]: the footprint fp cut by roof level. roof: (exterior, holes) rings in the footprint's CRS with z.
    Returns [(geometry, top_z, eave_z, roof_area, n_roof)], highest level first, or None (one level, or not split)."""
    if fp is None or fp.area < C["min_area"] or len(roof) < 2 or not np.isfinite(ground_z):
        return None
    fp = shapely.set_precision(fp, 0.01)
    polys = []
    for ext, holes in roof:
        if len(ext) < 4 or ext.shape[1] < 3:
            continue
        g = Polygon(ext[:, :2], [h[:, :2] for h in holes if len(h) >= 4])
        g = _poly(shapely.set_precision(g if g.is_valid else shapely.make_valid(g), 0.01))   # (on a 1 cm grid)
        if g.area > 0.01:                     # (vertical faces have no area seen from above)
            polys.append((g, float(ext[:, 2].max()), float(ext[:, 2].min()), area3d(ext)))
    if len(polys) < 2:
        return None
    if shapely.union_all([p[0] for p in polys]).intersection(fp).area < C["cover"] * fp.area:
        return None
    polys.sort(key=lambda p: -p[1])
    levels = []                               # [top, [polys]]
    for p in polys:
        if levels and p[1] >= levels[-1][0] - max(C["tol"], C["rel_tol"] * (levels[-1][0] - ground_z)):
            levels[-1][1].append(p)
        else:
            levels.append([p[1], [p]])
    if len(levels) < 2:
        return None
    w = C["min_width"]
    pieces, taken = [], None                  # [geometry, top, eave, roof_area, n]
    for top, ps in levels:
        g = shapely.union_all([p[0] for p in ps]).intersection(fp)
        if taken is not None:
            g = g.difference(taken)
        g = _clean(g, w)
        if g is None:
            continue
        taken = g if taken is None else _poly(taken.union(g))
        pieces.append([g, top, min(p[2] for p in ps), sum(p[3] for p in ps), len(ps)])
    rest = _clean(fp.difference(taken), 0) if taken is not None else None
    loose = list(getattr(rest, "geoms", [rest])) if rest is not None else []

    def neighbour(g, pool):
        """The piece of pool sharing the longest edge with g (else the nearest)."""
        best, bl = None, -1.0
        for i, q in enumerate(pool):
            l = g.boundary.intersection(q[0].boundary.buffer(0.05)).length
            if l > bl:
                best, bl = i, l
        if bl <= 0:
            best = min(range(len(pool)), key=lambda i: pool[i][0].distance(g))
        return best

    while True:                               # small or surplus levels go to their neighbours
        small = [i for i, q in enumerate(pieces) if q[0].area < C["min_part"]]
        if not small and len(pieces) > C["max_parts"]:
            small = [min(range(len(pieces)), key=lambda i: pieces[i][0].area)]
        if not small or len(pieces) < 2:
            break
        i = min(small, key=lambda i: pieces[i][0].area)
        q = pieces.pop(i)
        j = neighbour(q[0], pieces)
        pieces[j][0] = _poly(pieces[j][0].union(q[0]))
        pieces[j][4] += q[4]
    for g in loose:
        if pieces and g.area > 0:
            j = neighbour(g, pieces)
            pieces[j][0] = _poly(pieces[j][0].union(g))
    if len(pieces) < 2:
        return None
    out = []
    for g, top, eave, ra, n in pieces:
        out.append((_poly(shapely.make_valid(g.buffer(0))), top, eave, ra, n))
    return out


def split_rows(rows: list, C: dict) -> list:
    """[roof_split]: each row whose roof stands at several levels becomes a row per level (see the docstring)."""
    out = []
    for r in rows:
        roof = r.pop("_roof", None)
        try:
            lv = roof_levels(roof, r["geometry"], r.get("ground_z", np.nan), C) if C and roof else None
        except shapely.errors.GEOSException:             # (a topology error in a roof's polygons: left whole)
            lv = None
        if not lv:
            out.append(r)
            continue
        for k, (g, top, eave, ra, n) in enumerate(lv):
            out.append({**r, "geometry": g, "gml_id": f"{r['gml_id']}#r{k}", "parent_id": r["gml_id"], "part": True,
                        "roof_level": k, "roof_levels": len(lv), "roof_top_z": top, "eave_z": eave, "roof_area": ra,
                        "n_roof": n})
    return out


def plateau_lod1(el, row: dict, no_fp: bool, lod2: bool, pl: Plateau):
    """PLATEAU: footprint (no_fp), z values and lod of a solid from its lod0/lod1 geometry where LoD2 has none."""
    s1 = el.find("{*}lod1Solid")
    s1 = pl.project(polygons(s1)) if s1 is not None else []
    z = np.concatenate([e[:, 2] for e, _ in s1 if len(e) and e.shape[1] > 2]) if s1 else np.zeros(0)
    row["lod"] = 2 if lod2 else 1 if s1 else 0
    if no_fp:
        fp = None
        for key in ("lod0FootPrint", "lod0RoofEdge"):
            e = el.find(f"{{*}}{key}")
            if e is not None:
                fp = flat(pl.project(polygons(e)))
                if fp is not None:
                    row["fp_from"] = key
                    break
        if fp is None and len(z):
            bottom = [(e, h) for e, h in s1 if e.shape[1] > 2 and np.ptp(e[:, 2]) < 0.01 and e[:, 2].min() - z.min() < 0.01]
            fp = flat(bottom)
            row["fp_from"] = "lod1"
        row["_fp"] = fp
    if not len(z):
        return
    if np.isnan(row["ground_z"]):
        row["ground_z"] = float(z.min())
    if not lod2:
        row["roof_top_z"] = row["eave_z"] = float(z.max())
        row["roof_area"] = np.nan


def parse(fh, source: str, pl: Plateau | None = None, split: dict | None = None) -> list:
    """Rows of one CityGML stream, one cityObjectMember at a time. Each CityModel member is dropped once read, and an
    app:appearanceMember child by child as it streams (PLATEAU's texture block), so memory stays one building's."""
    rows = []
    stack = []
    app = 0
    for ev, el in ET.iterparse(fh, events=("start", "end")):
        if ev == "start":
            stack.append(el)
            if local(el.tag) == "appearanceMember":
                app += 1
            continue
        stack.pop()
        if app:
            if local(el.tag) == "appearanceMember":
                app -= 1
            el.clear()
            if len(stack) > 1 and len(stack[-1]) and stack[-1][-1] is el:
                del stack[-1][-1]
        if local(el.tag) == "Building" and not any(local(s.tag) in SOLID for s in stack):
            n0 = len(rows)
            building(el, rows, source, pl)
            rows[n0:] = split_rows(rows[n0:], split) if split else [{k: v for k, v in r.items() if k != "_roof"}
                                                                     for r in rows[n0:]]
        if len(stack) == 1:                 # a CityModel member (cityObjectMember, appearanceMember ...): done
            el.clear()
            if len(stack[0]) and stack[0][-1] is el:
                del stack[0][-1]
    return rows


def building(el, rows: list, source: str, pl):
    """A Building's rows: its own, or its parts' (and its own where it has surfaces of its own too)."""
    gid = el.get(f"{GML}id", "")
    if pl is not None:
        if gid in pl.seen:                            # read from an earlier file (or earlier in this one)
            pl.dup += 1
            el.clear()
            return
        pl.seen.add(gid)
    n0 = len(rows)
    parts = [p for c in el.findall("{*}consistsOfBuildingPart") for p in c if local(p.tag) == "BuildingPart"]
    if parts:
        inherited = {k: v for k, v in attrs(el, pl is not None).items() if k not in ("measuredHeight", "roofType", "name")}
        for p in parts:
            rows.append(solid_row(p, p.get(f"{GML}id", ""), gid, inherited, pl))
        if el.find("{*}boundedBy") is not None:      # a parent with surfaces of its own as well
            rows.append(solid_row(el, gid, "", {}, pl))
    else:
        rows.append(solid_row(el, gid, "", {}, pl))
    for r in rows[n0:]:
        r["tile"] = source
    el.clear()


def stem(path: Path) -> str:
    """A tile's name without .gz / .zip and .gml / .xml."""
    n = path.name
    for suf in (".gz", ".zip", ".gml", ".xml"):
        n = n[:-len(suf)] if n.lower().endswith(suf) else n
    return n


def open_tile(path: Path):
    return gzip.open(path, "rb") if path.suffix.lower() == ".gz" else open(path, "rb")


class CityGMLSource(FileSource):
    """A [sources.<name>] table with adapter = "citygml"."""

    def __init__(self, name: str):
        super().__init__(name)
        self.C = {**DEFAULTS, **CFG["sources"][name]}
        self.HEIGHTS = bool(self.C["height"])
        if self.C["flavour"] not in FLAVOURS:
            raise ValueError(f"[sources.{name}] flavour {self.C['flavour']!r}: known {FLAVOURS}")
        self.plateau = self.C["flavour"] == "plateau"
        self.pl = Plateau(self.C["crs"] or "EPSG:6668") if self.plateau else None
        rs = self.C["roof_split"]
        self.split = {**SPLIT_DEFAULTS, **rs} if rs else None

    def paths(self) -> list:
        p = self.C["path"]
        out = []
        for q in [p] if isinstance(p, str) else p:
            q = q if Path(q).is_absolute() else str(RAW / q)
            out += sorted(Path(x) for x in glob.glob(q)) if any(c in q for c in "*?[") else [Path(q)]
        if not out:
            raise FileNotFoundError(f"[sources.{self.name}] path {p!r}: no tiles")
        return out

    def fields_used(self, fields: list) -> list:
        return fields

    def members(self, z: zipfile.ZipFile) -> list:
        m = [n for n in z.namelist() if n.lower().endswith((".gml", ".xml", ".gml.gz", ".xml.gz"))]
        return [n for n in m if "/bldg/" in n and n.lower().endswith((".gml", ".gml.gz"))] if self.plateau else m

    def read(self, path: Path, bd: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        crs = self.C["crs"]
        pl = self.pl
        dup0 = pl.dup if pl is not None else 0
        t0 = time.time()
        rows = []
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as z:
                for m in self.members(z):
                    with z.open(m) as fh:
                        rows += parse(gzip.open(fh) if m.lower().endswith(".gz") else fh,
                                      stem(Path(m)) if pl is not None else path.stem, pl, self.split)
        else:
            with open_tile(path) as fh:
                rows += parse(fh, stem(path), pl, self.split)
        if pl is not None:
            crs = UTM                       # projected while parsing
            ndup = pl.dup - dup0
        if not crs:
            with (zipfile.ZipFile(path).open(next(m for m in zipfile.ZipFile(path).namelist() if m.lower().endswith((".gml", ".xml"))))
                  if path.suffix.lower() == ".zip" else open_tile(path)) as fh:
                head = fh.read(20000).decode("utf-8", "replace")
            m = re.search(r'srsName="[^"]*EPSG[^"]*?(\d{4,5})"', head)
            if not m:
                raise ValueError(f"[sources.{self.name}] {path.name}: set crs (srsName is not an EPSG code)")
            crs = f"EPSG:{m.group(1)}"
        df = pd.DataFrame(rows)
        if df.empty:
            if pl is not None:
                print(f"{path.name}: no new solids; duplicates skipped {ndup:,} ({time.time() - t0:.1f} s)", flush=True)
            return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=crs)
        nroof = int((df["fp_from"] == "roof").sum())
        nnone = int(df["geometry"].isna().sum())
        g = gpd.GeoDataFrame(df, geometry="geometry", crs=crs)
        for c in ("measuredHeight", "roofType"):
            if c not in g:
                g[c] = np.nan
        g["measuredHeight"] = pd.to_numeric(g["measuredHeight"], errors="coerce")
        msg = ""
        if pl is not None:
            plateau_columns(g)
            lod = g["lod"].value_counts()
            msg = (f"; LoD2 {lod.get(2, 0):,}, LoD1 {lod.get(1, 0):,}, LoD0 {lod.get(0, 0):,}; measuredHeight "
                   f"{int(g['measuredHeight'].notna().sum()):,}; duplicates skipped {ndup:,}")
        if self.split is not None:
            if "roof_level" not in g:
                g["roof_level"] = np.nan
            nb = g.loc[g["roof_level"].notna(), "parent_id"].nunique()
            msg += f"; roof_split: {nb:,} solids into {int(g['roof_level'].notna().sum()):,} levels"
        print(f"{path.name}: {len(g):,} solids ({int(g['part'].sum()):,} parts), footprint from roofs {nroof}, "
              f"none {nnone}{msg} ({time.time() - t0:.1f} s)", flush=True)
        return g[g.geometry.notna()]


def plateau_columns(g: pd.DataFrame):
    """PLATEAU: numeric storeys and areas, and the coded fields' English names (plateau_codelists.json)."""
    for c in ("storeysAboveGround", "storeysBelowGround", "buildingRoofEdgeArea"):
        if c in g:
            g[c] = pd.to_numeric(g[c], errors="coerce")
    tables = json.loads(CODELISTS.read_text(encoding="utf-8"))
    for f, t in tables.items():
        if not f.startswith("_") and f in g:
            g[f"{f}_name"] = g[f].map(lambda v: t[v][0] if isinstance(v, str) and v in t else None)


def instance(name: str) -> CityGMLSource:
    return CityGMLSource(name)
