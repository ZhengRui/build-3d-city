"""M1: option E snapped to the shores and the country-park edges, expressed as [districts] (relation + clip).

Inputs (no new downloads: run scripts/m1_fetch_boundary.py first, with the same CITY3D_OVERPASS_CACHE):
  plans/maps/hongkong.json            option E's hand-drawn polygon (WGS84)
  phase0/osm_coast.json, osm_water.json   OSM coastline and water over every option + 3 km (Phase 0's answers)
  the Overpass cache                  the nine districts' relations (01_osm's own boundary() query) and the
                                      protected areas (country parks, special areas, nature reserves)
Rules (UTM 50N):
  1. land = the coastline faces left of the lines (05_ground's rule, Phase 0's land_from_coastline) minus water;
  2. islands (land pieces not joined to the mainland or HK Island): in whole where over half lies in E, else out;
  3. country parks (each piece cut to the nine districts first: their boundaries follow the ridges) (boundary=protected_area with protect_class 5 or a "Country Park" name, and the rest of
     OSM's protected areas): each piece in whole where over half of it lies in E, else out: the edge then runs
     along the park's boundary, not through its hillside (a mostly-outside piece holding (within 300 m) one of Phase 0's summits
     (Phase 0's hills), such as Kowloon Peak's slopes in Ma On Shan Country Park, keeps the hand line);
  4. other land outside E but within GROW m of it is taken in (the hand line cut through Mei Foo, Hebe Haven and
     Sai Kung's streets); the districts' own boundaries (Kwai Tsing, Sha Tin, Southern beyond them) stop it;
  6. Kowloon's five urban districts whole (their boundaries are the ridge line);
  5. the sea keeps E's hand line (the harbour, Junk Bay, Port Shelter).
Writes demos/data/hongkong/boundary_E_snapped.geojson (the snapped polygon and per-district pieces) and prints
the [districts] block for city.toml: a plain relation id where the snapped polygon holds all of a district's land,
else {relation, clip = "data/boundary_districts.geojson"}: that file (WGS84, 6 decimals) holds the snapped polygon cut to
the district's box + 300 m (one ring, simplified 8 m) as the Feature named after the district."""
import json
import os
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import LineString, MultiPolygon, Polygon, box, mapping, shape
from shapely.ops import polygonize, transform, unary_union

ROOT = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True            # no __pycache__ in plans/maps
sys.path.insert(0, str(ROOT / "plans/maps"))
from size_options import land_from_coastline, water_polys  # noqa: E402

from city3d.common import overpass  # noqa: E402

GROW = 300.0
DATA = ROOT / "demos/data/hongkong"
fwd_t = Transformer.from_crs(4326, 32650, always_xy=True)
inv_t = Transformer.from_crs(32650, 4326, always_xy=True)
fwd = lambda lon, lat: fwd_t.transform(lon, lat)  # noqa: E731
to_utm = lambda g: transform(lambda x, y, z=None: fwd_t.transform(x, y), g)  # noqa: E731
to_ll = lambda g: transform(lambda x, y, z=None: inv_t.transform(x, y), g)  # noqa: E731

DIST = {"Central and Western": 2558879, "Wan Chai": 2558883, "Eastern": 2558880, "Yau Tsim Mong": 2670978,
        "Kowloon City": 2800201, "Sham Shui Po": 2800200, "Wong Tai Sin": 2800277, "Kwun Tong": 2800276,
        "Sai Kung": 8189562}
BOX = "(22.22,114.08,22.43,114.34)"


def relation(rid):
    r = overpass(f"""
        [out:json][timeout:120];
        rel({rid});
        out geom;
    """)["elements"][0]
    lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
             for m in r["members"] if m["type"] == "way" and m.get("role") == "outer"]
    return to_utm(unary_union(list(polygonize(unary_union(lines)))))


def parts(g):
    return list(getattr(g, "geoms", [g])) if not g.is_empty else []


opts = json.loads((ROOT / "plans/maps/hongkong.json").read_text())["options"]
E = to_utm(shape(next(o for o in opts if o["id"] == "E")["geom"]))
ph = DATA / "phase0"
coast = json.loads((ph / "osm_coast.json").read_text())
lines = [LineString([fwd(p["lon"], p["lat"]) for p in el["geometry"]]) for el in coast["elements"] if "geometry" in el]
water = water_polys(json.loads((ph / "osm_water.json").read_text()), fwd)
area = box(*E.buffer(2500).bounds)          # inside the coastline answer's box (E and the other options + 3 km)
land_all = land_from_coastline(lines, area)        # before inland water: islands are pieces of this
land = land_all.difference(water)
D = {n: relation(r) for n, r in DIST.items()}
dist_all = unary_union(list(D.values()))

# protected areas
res = overpass(f"""[out:json][timeout:300];
(way["boundary"="protected_area"]{BOX}; rel["boundary"="protected_area"]{BOX};
 way["leisure"="nature_reserve"]{BOX}; rel["leisure"="nature_reserve"]{BOX};
 way["boundary"="national_park"]{BOX}; rel["boundary"="national_park"]{BOX};);
out geom;""")
parks = []
for e in res["elements"]:
    t = e.get("tags", {})
    one = {"type": "x", "elements": [e]}
    g = water_polys(one, fwd)
    if g.is_empty:
        continue
    parks.append((t.get("name:en") or t.get("name") or f"{e['type']}{e['id']}", make_valid(g).intersection(land_all)))
cp = [(n, g) for n, g in parks if "country park" in n.lower() or "special area" in n.lower()]
print(f"protected areas: {len(parks)}, country parks / special areas: {len(cp)}: "
      + ", ".join(sorted({n for n, _ in cp})))

from shapely.geometry import Point  # noqa: E402
HILLS = [(h["name"], Point(fwd(h["lon"], h["lat"]))) for h in json.loads((ph / "research.json").read_text())["hills"]]
S = E
log = []
# 2. islands: land_all pieces; the two biggest (Kowloon/New Territories mainland, HK Island) are not islands
pieces = sorted(parts(land_all), key=lambda p: -p.area)
for p in pieces[2:]:
    if p.area < 2000 or not p.intersects(E.buffer(2000)):
        continue
    share = p.intersection(E).area / p.area
    if 0 < share < 1:
        S = S.union(p) if share > 0.5 else S.difference(p)
        log.append(f"island {p.area / 1e6:.3f} km² ({share:.0%} in E): {'in' if share > 0.5 else 'out'}")
# 3. country parks (each connected piece)
for n, g in cp:
    # the park's piece inside the nine districts: the urban districts' boundaries run along the ridges (Lion Rock,
    # Beacon Hill, Kowloon Peak), so a park straddling a ridge is judged by its own side of it
    for p in parts(g.intersection(dist_all)):
        if p.area < 5000:
            continue
        share = p.intersection(E).area / p.area
        if 0 < share < 1:
            peak = [h for h, q in HILLS if p.buffer(300).contains(q)]
            if share > 0.5:
                S = S.union(p)
                verdict = "in"
            elif peak:              # a mostly-outside piece holding (within 300 m) a summit: the hand line stays
                verdict = f"kept as drawn (holds {', '.join(peak)})"
            else:
                S = S.difference(p)
                verdict = "out"
            log.append(f"park {n} piece {p.area / 1e6:.2f} km² ({share:.0%} in E): {verdict}")
park_u = unary_union([g for _, g in cp]) if cp else Polygon()
# 4. town edges: non-park land within GROW m outside E, inside the nine districts
grow = E.buffer(GROW).difference(E).intersection(land).difference(park_u).intersection(dist_all)
S = S.union(grow)
log.append(f"grown by {GROW:.0f} m over non-park land: {grow.area / 1e6:.2f} km²")
# 5. Kowloon's five districts whole: their northern and eastern boundaries are the Lion Rock, Beacon Hill and
# Kowloon Peak ridge line itself (the hand line ran a little below it; Phase 0's D/E went "up to the ridge")
for n in ("Yau Tsim Mong", "Kowloon City", "Sham Shui Po", "Wong Tai Sin", "Kwun Tong"):
    add = D[n].difference(S)
    log.append(f"{n} whole: + {add.intersection(land).area / 1e6:.2f} km² of land")
    S = S.union(D[n])
S = make_valid(S.buffer(150).buffer(-150))   # closing: slits under 300 m wide (the hand line's notch at Kowloon Peak) filled
S = max(parts(S), key=lambda p: p.area) if S.geom_type == "MultiPolygon" else S
holes = len(S.interiors)
S = Polygon(S.exterior)                  # a clip is one ring: holes (an excluded hollow) dropped
print("\n".join(log))
print(f"holes dropped: {holes}")

land_E = E.intersection(land).intersection(dist_all).area / 1e6
land_S = S.intersection(land).intersection(dist_all).area / 1e6
print(f"land in the nine districts: hand-drawn E {land_E:.1f} km² (Phase 0: 125.6 over the whole polygon), "
      f"snapped {land_S:.1f} km²; polygon {S.area / 1e6:.1f} km²")

feats, clips, toml = [], [], ["[districts]"]
tot = 0.0
for n, g in D.items():
    dl = g.intersection(land)
    inside = dl.intersection(S)
    share = inside.area / dl.area if dl.area else 1.0
    tot += inside.area
    key = f'"{n}"' if " " in n else n
    if share > 0.999:
        toml.append(f"{key} = {DIST[n]}")
        clip = None
    else:
        c = S.intersection(box(*g.buffer(300).bounds)).simplify(8)
        c = max(parts(c), key=lambda p: p.area)
        c = Polygon(c.exterior)
        ll = [[round(x, 6), round(y, 6)] for x, y in to_ll(c).exterior.coords]
        clips.append({"type": "Feature", "properties": {"name": n, "relation": DIST[n]},
                      "geometry": {"type": "Polygon", "coordinates": [ll]}})
        toml.append(f'{key} = {{ relation = {DIST[n]}, clip = "data/boundary_districts.geojson" }}')
        clip = len(ll)
    print(f"{n}: district land {dl.area / 1e6:.1f} km², in the boundary {inside.area / 1e6:.1f} km² "
          f"({share:.0%}){'' if clip is None else f', clip of {clip} points'}")
    feats.append({"type": "Feature", "properties": {"name": n, "relation": DIST[n], "land_km2": round(dl.area / 1e6, 2),
                  "in_km2": round(inside.area / 1e6, 2), "clip_points": clip},
                  "geometry": mapping(to_ll(g.intersection(S)))})
print(f"land in the scene: {tot / 1e6:.1f} km²")
feats.insert(0, {"type": "Feature", "properties": {"name": "E snapped", "land_km2": round(tot / 1e6, 2),
                 "polygon_km2": round(S.area / 1e6, 2)}, "geometry": mapping(to_ll(S))})
(DATA / "boundary_E_snapped.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
(DATA / "districts_E.toml").write_text("\n".join(toml) + "\n")
CLIPS = Path(__file__).resolve().parents[1] / "data/boundary_districts.geojson"
CLIPS.write_text(json.dumps({"type": "FeatureCollection", "features": clips}, separators=(",", ":")) + "\n")
print(f"wrote {CLIPS} ({len(clips)} district clips)")
print(f"wrote {DATA / 'boundary_E_snapped.geojson'} and districts_E.toml")

# a map for the README: the hand line, the snapped polygon, the land and the districts' pieces
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import geopandas as gpd  # noqa: E402
fig, ax = plt.subplots(figsize=(11, 8.5))
gpd.GeoSeries([land.intersection(box(*S.buffer(3000).bounds))], crs=32650).plot(ax=ax, color="#e8e4d8", lw=0)
gpd.GeoSeries([park_u.intersection(box(*S.buffer(3000).bounds))], crs=32650).plot(ax=ax, color="#b9d7a8", lw=0)
gpd.GeoSeries([g.intersection(S) for g in D.values()], crs=32650).plot(ax=ax, facecolor="none", edgecolor="#777", lw=0.5)
gpd.GeoSeries([S], crs=32650).boundary.plot(ax=ax, color="#c0392b", lw=1.4)
gpd.GeoSeries([E], crs=32650).boundary.plot(ax=ax, color="#1f4e9c", lw=0.8, ls="--")
ax.set_title("Hong Kong E: hand-drawn (blue dashed) and snapped (red); land beige, country parks green, districts grey")
ax.set_axis_off()
fig.tight_layout()
CK = Path(__file__).resolve().parents[1] / "checks"
fig.savefig(CK / "m1_boundary.png", dpi=80)
print(f"wrote {CK / 'm1_boundary.png'}")
