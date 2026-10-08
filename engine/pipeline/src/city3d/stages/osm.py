"""01_osm: fetch the district boundaries (city.toml [districts]) and all OSM buildings inside them.

Writes to the data folder:
  boundary.gpkg       one polygon per district (WGS84); a district is an OSM relation, or the part of one
                      inside a polygon ({relation = id, clip = [[lon, lat], ...]}, or clip = "<file>.geojson":
                      the Feature named like the district in a GeoJSON FeatureCollection, Polygon or MultiPolygon)
  osm_buildings.gpkg  building footprints with height / building:levels / layer / location tags, and their
                      district (common.load_osm drops the underground ones); with [osm] underground_drop also the
                      underground / level tags, with [osm] min_height also min_height / building:min_level
  osm_parts.gpkg      with [buildings] parts = true: the building:part outlines (a tower's setbacks, podium,
                      crown) with height / min_height / building:levels / building:min_level / roof tags,
                      where mappers drew them (Manhattan's skyscrapers mostly are); 04_buildings builds those
                      buildings from their parts
"""
import functools
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiPolygon, Polygon, shape
from shapely.ops import polygonize, unary_union

from ..common import CFG, CITY, DATA, DISTRICTS, overpass

DATA.mkdir(parents=True, exist_ok=True)
# [osm] area = false: ask for a district's buildings by the bounding box of its polygon and keep those meeting it,
# not by Overpass's area(): for a server without areas (a local Overpass whose area dispatcher is not running:
# Berlin's container answers "open64: ... osm3s_areas"). The same buildings (a way is in an area when it meets it)
AREA = CFG.get("osm", {}).get("area", True)
# [osm] underground_drop / min_height: also keep the underground, level / min_height, building:min_level tags (04_buildings
# drops the underground outlines, raises a building from its min_height); off: the columns are exactly as before
UNDERGROUND_DROP = CFG.get("osm", {}).get("underground_drop", False)
MIN_HEIGHT = CFG.get("osm", {}).get("min_height", False)


def boundary(rel_id: int) -> gpd.GeoDataFrame:
    res = overpass(f"""
        [out:json][timeout:120];
        rel({rel_id});
        out geom;
    """)
    rel = res["elements"][0]
    lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
             for m in rel["members"] if m["type"] == "way" and m.get("role") == "outer"]
    poly = unary_union(list(polygonize(unary_union(lines))))
    return gpd.GeoDataFrame({"name": [rel["tags"]["name"]], "osm_id": [rel["id"]]},
                            geometry=[poly], crs="EPSG:4326")


PART_TAGS = {"min_height": "min_height", "min_level": "building:min_level", "roof_shape": "roof:shape",
             "roof_height": "roof:height", "colour": "building:colour", "material": "building:material",
             "part": "building:part"}


def buildings(area_rel_id: int, key: str = "building", clip=None, poly=None) -> gpd.GeoDataFrame:
    """`clip`: the district's clip geometry (WGS84; district_spec), or None."""
    # a clipped district: only the clip's box of the relation (all of Brooklyn would be 330,000 buildings)
    bb = ""
    if clip is not None:
        lo0, la0, lo1, la1 = clip.bounds
        bb = f"({la0:.5f},{lo0:.5f},{la1:.5f},{lo1:.5f})"
    if AREA or poly is None:
        res = overpass(f"""
            [out:json][timeout:600];
            area({3600000000 + area_rel_id})->.a;
            (way["{key}"](area.a){bb}; rel["{key}"]["type"="multipolygon"](area.a){bb};);
            out geom;
        """)
    else:                           # by the district polygon's box; main() keeps what meets the polygon
        w, s_, e, n = poly.bounds
        bb = f"({s_:.6f},{w:.6f},{n:.6f},{e:.6f})"
        res = overpass(f"""
            [out:json][timeout:600];
            (way["{key}"]{bb}; rel["{key}"]["type"="multipolygon"]{bb};);
            out geom;
        """)
    rows = []
    for e in res["elements"]:
        t = e.get("tags", {})
        if e["type"] == "way":
            pts = [(p["lon"], p["lat"]) for p in e["geometry"]]
            if len(pts) < 4:
                continue
            geom = shape({"type": "Polygon", "coordinates": [pts]})
        else:
            outers = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                      for m in e["members"] if m.get("role") == "outer" and "geometry" in m]
            inners = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                      for m in e["members"] if m.get("role") == "inner" and "geometry" in m]
            geom = unary_union(list(polygonize(unary_union(outers)))) if outers else None
            if geom is not None and inners:
                geom = geom.difference(unary_union(list(polygonize(unary_union(inners)))))
        if geom is None or geom.is_empty:
            continue
        extra = {k: t.get(v) for k, v in PART_TAGS.items()} if key == "building:part" else {}
        if MIN_HEIGHT and key != "building:part":
            extra.update({k: t.get(v) for k, v in PART_TAGS.items() if k in ("min_height", "min_level")})
        if UNDERGROUND_DROP:
            extra.update({"underground": t.get("underground"), "level": t.get("level")})
        rows.append({
            "osm_id": f'{e["type"][0]}{e["id"]}',
            "building": t.get("building"),
            "name": t.get("name"),
            "height": t.get("height"),
            "levels": t.get("building:levels"),
            "layer": t.get("layer"),
            "location": t.get("location"),
            **extra,
            "geometry": geom.buffer(0),
        })
    if not rows:                    # none (a district without building:part outlines)
        return gpd.GeoDataFrame({"osm_id": [], "building": []}, geometry=[], crs="EPSG:4326")
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


@functools.cache
def _clip_features(path: Path) -> list:
    """The features of a clip file: [(name, geometry)], the geometries WGS84 Polygons / MultiPolygons."""
    if not path.is_file():
        raise FileNotFoundError(f"[districts] clip file {str(path)!r} not found")
    fc = json.loads(path.read_text())
    if fc.get("type") != "FeatureCollection":
        raise ValueError(f"[districts] clip file {str(path)!r} is not a GeoJSON FeatureCollection")
    return [((f.get("properties") or {}).get("name"), shape(f["geometry"])) for f in fc.get("features", [])
            if f.get("geometry")]


def file_clip(name: str, spec: str, city=None):
    """The clip of district `name` from a GeoJSON FeatureCollection: the Feature whose properties.name is `name`
    (several of that name are united). `spec` is a path relative to the city folder, or absolute."""
    path = Path(spec)
    if not path.is_absolute():
        path = Path(city if city is not None else CITY) / path
    feats = _clip_features(path)
    geoms = [g for n, g in feats if n == name]
    if not geoms:
        have = ", ".join(sorted(str(n) for n, _ in feats if n is not None)) or "none"
        raise ValueError(f"[districts] {name!r}: no Feature with properties.name = {name!r} in the clip file "
                         f"{str(path)!r} (names there: {have})")
    for g in geoms:
        if not isinstance(g, (Polygon, MultiPolygon)):
            raise ValueError(f"[districts] {name!r}: the Feature in {str(path)!r} is a {g.geom_type}, "
                             "not a Polygon or MultiPolygon")
    g = geoms[0] if len(geoms) == 1 else unary_union(geoms)
    if g.is_empty:
        raise ValueError(f"[districts] {name!r}: the Feature in {str(path)!r} has an empty geometry")
    return g if g.is_valid else g.buffer(0)


def district_spec(v, name=None, city=None):
    """A [districts] value -> (relation id, clip geometry or None). The value is an OSM relation id, or
    {relation = id, clip = ...} for the part of a relation inside a clip: a ring [[lon, lat], ...] (the Heights
    and Downtown of Jersey City, north-west Brooklyn), or a path (relative to the city folder, or absolute) to a
    GeoJSON FeatureCollection whose Feature with properties.name = `name` (the district's key) is the clip,
    a Polygon or MultiPolygon (Singapore's subzones; keeps city.toml free of generated data)."""
    if isinstance(v, int):
        return v, None
    clip = v.get("clip")
    if isinstance(clip, str):
        if not clip:
            return v["relation"], None
        if name is None:
            raise ValueError(f"[districts] clip = {clip!r} is a file: the district's name is needed to pick its Feature")
        return v["relation"], file_clip(name, clip, city)
    return v["relation"], (Polygon(clip) if clip else None)


def main():
    bs, gs, polys = [], [], {}
    for name, v in DISTRICTS.items():
        rel_id, clip = district_spec(v, name)
        b = boundary(rel_id)
        if clip is not None:
            b["geometry"] = b.geometry.intersection(clip)
        b["name"] = name
        area_km2 = b.to_crs(b.estimate_utm_crs()).area.iloc[0] / 1e6
        polys[name] = b.geometry.iloc[0]
        g = buildings(rel_id, clip=clip, poly=polys[name])
        g = g[g.intersects(b.geometry.iloc[0])].assign(district=name)
        print(f"{name}: relation {rel_id}, {area_km2:.1f} km², {len(g):,} OSM buildings")
        bs.append(b)
        gs.append(g)
    gpd.GeoDataFrame(pd.concat(bs, ignore_index=True), crs="EPSG:4326").to_file(DATA / "boundary.gpkg")
    g = gpd.GeoDataFrame(pd.concat(gs, ignore_index=True), crs="EPSG:4326").drop_duplicates("osm_id")
    g.to_file(DATA / "osm_buildings.gpkg")
    print(f"osm buildings: {len(g)}  with height: {g.height.notna().sum()}  "
          f"with levels: {g.levels.notna().sum()}")
    if CFG["buildings"]["parts"]:
        ps = []
        for name, v in DISTRICTS.items():
            rel_id, clip = district_spec(v, name)
            p = buildings(rel_id, "building:part", clip, polys[name])
            if clip is not None:
                p = p[p.intersects(clip)]
            if not AREA and len(p):
                p = p[p.intersects(polys[name])]
            ps.append(p.assign(district=name))
        p = gpd.GeoDataFrame(pd.concat(ps, ignore_index=True), crs="EPSG:4326").drop_duplicates("osm_id")
        p.to_file(DATA / "osm_parts.gpkg")
        print(f"osm building parts: {len(p)}  with height: {p.height.notna().sum()}  "
              f"with min_height: {p.min_height.notna().sum()}")
    print(json.dumps(g.building.value_counts().head(10).to_dict(), ensure_ascii=False))
