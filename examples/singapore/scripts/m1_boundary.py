"""M1: Singapore's boundary (option D, the user's choice of 6 Oct 2026) from URA's Master Plan 2019 subzones.

The engine's [districts] are OSM relations, optionally cut by a polygon ({relation, clip}). Singapore's units are
URA's subzones, which are not OSM relations by URA's names, so every district here is the country relation
(Singapore, r536780, which reaches into the territorial sea and so holds every subzone) clipped to the union of
the chosen subzones of one planning area: the district polygons ARE the subzones (that is the snap). The union per
planning area is simplified as a coverage (shared edges stay shared, no slivers) by TOL m.

Writes (relative to demos/singapore):
  data/boundary_districts.geojson  one feature per district (WGS84, coordinates rounded to 6 decimals, ~0.1 m), the
                                   clips city.toml's [districts] read ({relation, clip = "<this file>"}, by name)
and prints the [districts] block's comment lines (subzones, area, vertices) for city.toml,
each district's area (EPSG:3414), the total, and the land share (less OSM water, if phase0 has it).
Run: uv run python scripts/m1_boundary.py
"""
import json
import string
from pathlib import Path

import geopandas as gpd
import shapely
from shapely.geometry import box

HERE = Path(__file__).resolve().parent.parent
RAW = HERE.parent / "data" / "singapore" / "raw"
COUNTRY = 536780            # OSM relation "Singapore" (admin_level 2)
TOL = 5.0                   # m, coverage simplification
CLOSE = 40.0                # m: parts of a planning area closer than 2x this are joined (canals, islets)
MARITIME_EAST = 103.8085    # Maritime Square only east of this longitude (the boundary note)

# planning area -> subzones (None: all of them); option D of the Phase 0 boundary note
CHOSEN = {
    "DOWNTOWN CORE": None, "MARINA SOUTH": None, "STRAITS VIEW": None, "MUSEUM": None, "SINGAPORE RIVER": None,
    "OUTRAM": None, "ROCHOR": None, "MARINA EAST": None,
    "KALLANG": ["TANJONG RHU", "CRAWFORD"],
    "ORCHARD": None, "RIVER VALLEY": None,
    "NEWTON": ["ISTANA NEGARA"],
    "BUKIT MERAH": ["TIONG BAHRU", "CITY TERMINALS", "EVERTON PARK", "SINGAPORE GENERAL HOSPITAL",
                    "TELOK BLANGAH RISE", "MARITIME SQUARE"],
    "SOUTHERN ISLANDS": ["SENTOSA"],
}
NAMES = {"DOWNTOWN CORE": "Downtown Core", "MARINA SOUTH": "Marina South", "STRAITS VIEW": "Straits View",
         "MUSEUM": "Museum", "SINGAPORE RIVER": "Singapore River", "OUTRAM": "Outram", "ROCHOR": "Rochor",
         "MARINA EAST": "Marina East", "KALLANG": "Kallang (Tanjong Rhu)", "ORCHARD": "Orchard",
         "RIVER VALLEY": "River Valley", "NEWTON": "Newton (Istana Negara)",
         "BUKIT MERAH": "Bukit Merah (Tiong Bahru to the City Terminals)", "SOUTHERN ISLANDS": "Sentosa"}


def main():
    sz = gpd.read_file(RAW / "MP2019_subzone_nosea.geojson")
    sel = sz[sz.PLN_AREA_N.isin(CHOSEN) & sz.apply(
        lambda r: r.PLN_AREA_N in CHOSEN and (CHOSEN[r.PLN_AREA_N] is None or r.SUBZONE_N in CHOSEN[r.PLN_AREA_N]), axis=1)].copy()
    ms = sel.SUBZONE_N == "MARITIME SQUARE"
    sel.loc[ms, "geometry"] = sel.loc[ms].geometry.intersection(box(MARITIME_EAST, 1.0, 104.5, 1.6))
    want = sum(len(v) if v else (sz.PLN_AREA_N == k).sum() for k, v in CHOSEN.items())
    assert len(sel) == want, (len(sel), want)
    sel = sel.to_crs(3414)
    raw_area = sel.area.sum() / 1e6
    pa = sel.dissolve("PLN_AREA_N").reset_index()
    pa["geometry"] = shapely.coverage_simplify(shapely.make_valid(pa.geometry.values), TOL)
    rows, lines = [], []
    for _, r in pa.iterrows():
        g = r.geometry
        if g.geom_type == "MultiPolygon":       # one clip is one ring: join parts across narrow water
            g = shapely.union(g, g.buffer(CLOSE, join_style="mitre").buffer(-CLOSE, join_style="mitre"))
        parts = sorted(getattr(g, "geoms", [g]), key=lambda p: -p.area)
        for i, p in enumerate(parts):
            if p.area < 50000:      # pieces under 5 ha (Sentosa's beach islets, a 2 ha islet, no buildings): dropped
                print(f"  dropped a {p.area:.0f} m² piece of {r.PLN_AREA_N} at {gpd.GeoSeries([p.representative_point()], crs=3414).to_crs(4326).iloc[0]}")
                continue
            name = NAMES[r.PLN_AREA_N]
            if len(parts) > 1 and i:          # a second piece: named by the subzone it lies in
                inside = sel[(sel.PLN_AREA_N == r.PLN_AREA_N) & sel.contains(p.representative_point())].SUBZONE_N
                base = NAMES[r.PLN_AREA_N].split(" (")[0]
                sub = string.capwords(inside.iloc[0]) if len(inside) else str(i + 1)
                name = f"{base} ({'islet' if sub == base else sub})"
            if len(p.interiors):
                print(f"  {name}: {len(p.interiors)} holes ({sum(shapely.Polygon(h).area for h in p.interiors):.0f} m²) "
                      "filled: a clip is one ring")
            rows.append({"name": name, "pln_area": r.PLN_AREA_N,
                         "subzones": ", ".join(sorted(sel[sel.PLN_AREA_N == r.PLN_AREA_N].SUBZONE_N)),
                         "km2": round(p.area / 1e6, 3), "geometry": shapely.Polygon(p.exterior)})
    d = gpd.GeoDataFrame(rows, crs=3414)
    w = d.to_crs(4326)
    for (_, r), (_, rw) in zip(d.iterrows(), w.iterrows()):
        ring = [[round(x, 6), round(y, 6)] for x, y in rw.geometry.exterior.coords]
        sub = sel[sel.intersects(r.geometry.buffer(-20))].SUBZONE_N if r.km2 > 0.05 else [r.subzones]
        lines.append(f"# {', '.join(string.capwords(x) for x in sorted(sub))}; {r.km2:.2f} km², {len(ring)} vertices")
        lines.append(f'"{r["name"]}" = {{ relation = {COUNTRY}, clip = "data/boundary_districts.geojson" }}')
    (HERE / "data").mkdir(exist_ok=True)
    # rounded as the inline clips were (6 decimals), so the file clips the relation exactly as they did
    w["geometry"] = [shapely.Polygon([(round(x, 6), round(y, 6)) for x, y in g.exterior.coords]) for g in w.geometry]
    w.to_file(HERE / "data" / "boundary_districts.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    print("\n".join(lines))
    total = d.area.sum() / 1e6
    print(d[["name", "km2"]].to_string(index=False))
    print(f"subzones {len(sel)}, raw area {raw_area:.2f} km², districts {len(d)}, simplified {total:.2f} km², "
          f"vertices {sum(len(g.exterior.coords) for g in d.geometry)}")
    water = HERE.parent / "data" / "singapore" / "phase0" / "osm_water.json"
    if water.exists():
        from shapely.geometry import LineString, Polygon
        from shapely.ops import polygonize, unary_union
        polys = []
        for e in json.loads(water.read_text())["elements"]:
            if e["type"] == "way" and len(e.get("geometry", [])) >= 4 and e["geometry"][0] == e["geometry"][-1]:
                polys.append(Polygon([(p["lon"], p["lat"]) for p in e["geometry"]]))
            elif e["type"] == "relation":
                ls = lambda role: [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                                   for m in e["members"] if m.get("role") == role and "geometry" in m]
                o = unary_union(list(polygonize(unary_union(ls("outer")))))
                i = ls("inner")
                polys.append(o.difference(unary_union(list(polygonize(unary_union(i))))) if i else o)
        wg = gpd.GeoSeries(polys, crs=4326).to_crs(3414).make_valid().union_all()
        u = d.union_all()
        print(f"OSM water inside: {u.intersection(wg).area / 1e6:.2f} km², land {(u.area - u.intersection(wg).area) / 1e6:.2f} km²")


if __name__ == "__main__":
    main()
