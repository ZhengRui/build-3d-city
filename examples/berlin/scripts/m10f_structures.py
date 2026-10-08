"""M10 fix round (builder R): small landmarks the table lacks, as [[structures]] figures written to
generated/structures-m10f.toml (city.toml `include`s it; re-run after editing the numbers here, after
05a_terrain and m4h/m4t; then 06_tiles):

- the Neue Nationalgalerie (Mies, 1968): its LoD2 hall and the four canopy pieces of its roof plate's overhang are
  excluded in [buildings] (they read as a beige hollow box): the dark glass hall (50.4 m square, set back 7.2 m), the
  black steel roof plate (64.8 m square, 1.8 m deep) and its eight columns, two per side;
- Checkpoint Charlie: the replica US Army booth (white, about 3.5 x 2.5 m), its sandbags and the sign
  ("You are leaving the American sector") on its mast, in the middle of Friedrichstraße (OSM node 417346627);
- the Soviet War Memorial in Treptower Park (Vuchetich, 1949): the mound (OSM's 60 m grass ring), the white
  mausoleum plinth (OSM w142701713, 9 m), the 12 m soldier with the child and the lowered sword (a few tubes), and
  the two lowered red granite banners at the entrance (OSM w142701792 and w1002636043, 14 m);
- the Alte Nationalgalerie's temple front: eight Corinthian columns on the high podium at the south end, the
  entablature and the pediment, the double stair (the LoD2 body has none of it).

Positions from the table (buildings.gpkg) and OSM (the local Overpass, cached in <data>/m10f_osm.json), heights from
landmarks_berlin.csv, Wikipedia and the photos (refs/). Run from demos/berlin: `uv run python scripts/m10f_structures.py`.
"""
import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon

HERE = Path(__file__).resolve().parents[1]
DATA = HERE.parent / "data" / "berlin"
UTM = 32633
TO_UTM = Transformer.from_crs(4326, UTM, always_xy=True)
TO_LL = Transformer.from_crs(UTM, 4326, always_xy=True)
OVERPASS = "http://127.0.0.1:8793/api/interpreter"


def utm(lon, lat):
    return np.array(TO_UTM.transform(lon, lat))


def ll(p):
    lon, lat = TO_LL.transform(float(p[0]), float(p[1]))
    return [round(lon, 7), round(lat, 7)]


def f(x):
    return f"{x:.10g}" if isinstance(x, float) else str(x)


def arr(v):
    if isinstance(v, (list, tuple, np.ndarray)):
        return "[" + ", ".join(arr(x) for x in v) + "]"
    if isinstance(v, str):
        return f'"{v}"'
    return f(round(float(v), 3))


def square(h, cx=0.0, cz=0.0):
    return [[cx - h, cz - h], [cx + h, cz - h], [cx + h, cz + h], [cx - h, cz + h]]


def ring(r, n=8, phase=None, cx=0.0, cz=0.0):
    phase = math.pi / n if phase is None else phase
    return [[round(cx + r * math.cos(phase + 2 * math.pi * i / n), 3), round(cz + r * math.sin(phase + 2 * math.pi * i / n), 3)]
            for i in range(n)]


def frame_of(facing):
    az = math.radians(facing)
    fwd = np.array([math.sin(az), math.cos(az)])
    return np.array([fwd[1], -fwd[0]]), fwd


def local(p, origin, facing=0.0):
    right, fwd = frame_of(facing)
    d = np.asarray(p, float) - origin
    return [round(float(d @ right), 3), round(float(d @ fwd), 3)]


def bearing(u):
    return math.degrees(math.atan2(u[0], u[1])) % 360


def rect(geom):
    r = geom.minimum_rotated_rectangle
    c = np.array(r.exterior.coords)[:4]
    e = [c[1] - c[0], c[2] - c[1]]
    i = int(np.argmax([np.hypot(*v) for v in e]))
    L, W = float(np.hypot(*e[i])), float(np.hypot(*e[1 - i]))
    u = e[i] / L
    return np.array(r.centroid.coords[0]), u, np.array([-u[1], u[0]]), L, W


blocks = []


def figure(name, at_utm, facing=0.0, colour="#b0b0b0", top=None, style="floodlit", variant=0.5,
           sections=None, tubes=None, boxes=None, prisms=None, slabs=None, segments=None, note=None):
    ys = [s[0] for s in sections or []] + [p[2] for p in prisms or []] + [b[1] + b[4] / 2 for b in boxes or []] \
        + [max(t[0][1], t[1][1]) for t in tubes or []] + [max(q[1] for q in s[0]) for s in slabs or []]
    top = top or max(ys + [1.0])
    out = [f"# {line}" for line in (note or "").split("\n") if note]
    out += ["[[structures]]", 'kind = "figure"', f'name = "{name}"', "at = [%.7f, %.7f]" % tuple(ll(at_utm)),
            f"facing = {f(round(float(facing), 2))}", f'style = "{style}"', f"variant = {variant}", f'colour = "{colour}"',
            f"top = {f(round(float(top), 2))}"]
    if segments:
        out.append(f"segments = {int(segments)}")
    for key, v in (("sections", sections), ("tubes", tubes), ("boxes", boxes), ("prisms", prisms), ("slabs", slabs)):
        if v:
            out.append(f"{key} = [" + ",\n    ".join(arr(x) for x in v) + "]")
    blocks.append("\n".join(out) + "\n")


OSM_WAYS = {142701713: "Soviet War Memorial mausoleum", 142701730: "the mound's grass", 142701792: "banner (west)",
            1002636043: "banner (east)", 1504490305: "Berlin Wall (Bernauer Straße)", 1504490306: "Berlin Wall (Bernauer Straße)",
            1504490315: "Berlin Wall (Bernauer Straße)", 1504490317: "Berlin Wall (Bernauer Straße)",
            1504490318: "Berlin Wall (Bernauer Straße)"}


def osm_query():
    cache = DATA / "m10f_osm.json"
    have = json.loads(cache.read_text()) if cache.exists() else {}
    missing = [i for i in OSM_WAYS if str(i) not in have]
    if missing:
        q = f"[out:json][timeout:90];way(id:{','.join(map(str, missing))});out tags geom;"
        req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                     headers={"User-Agent": "3D-Fun berlin m10f"})
        els = json.loads(urllib.request.urlopen(req, timeout=120).read())["elements"]
        have.update({str(e["id"]): {"tags": e.get("tags", {}), "geom": [[g["lon"], g["lat"]] for g in e["geometry"]]} for e in els})
        cache.write_text(json.dumps(have))
    return have


OSM = osm_query()


def osm_line(i):
    return np.array([TO_UTM.transform(*q) for q in OSM[str(i)]["geom"]])


def osm_poly(i):
    return Polygon([TO_UTM.transform(*q) for q in OSM[str(i)]["geom"]])


B = gpd.read_file(DATA / "buildings.gpkg", bbox=(13.36, 52.48, 13.48, 52.53)).to_crs(UTM)
L2 = gpd.read_file(DATA / "lod2_buildings.gpkg", bbox=(13.365, 52.505, 13.37, 52.509)).to_crs(UTM)


def piece(gml, table=B):
    s = table[table.gml_id == gml]
    if not len(s):
        raise SystemExit(f"no piece {gml}")
    return s.iloc[0]


# ------------------------------------------------------------------ the Neue Nationalgalerie
# the hall piece's rectangle (the LoD2's, excluded) gives the centre and the axes; the plate 64.8 m square, its top at
# the canopies' 10.4 m (the LoD2's), 1.8 m deep; the glass walls 7.2 m in from its edge; eight cruciform steel columns,
# two per side, 14.4 m either side of the middle (the corners cantilevered 18 m); the plinth (its 4.6 m LoD2 piece to
# the west) stays, tinted granite in landmark_facades.csv
hall = piece("DEBE3DLm1PkVj2Jm", L2)
c, u, v, Ln, Wd = rect(hall.geometry)
GLASS, STEEL = "#39404a", "#232427"
cols = []
for s in (-1, 1):
    for t in (-14.4, 14.4):
        cols.append([[t, 0.0, s * 31.2], [t, 8.6, s * 31.2], 0.45, STEEL])
        cols.append([[s * 31.2, 0.0, t], [s * 31.2, 8.6, t], 0.45, STEEL])
figure("Neue Nationalgalerie", c, bearing(u), STEEL, 10.4, style="spire", variant=0.5,
       prisms=[[square(25.2), 0.0, 8.6, GLASS], [square(32.4), 8.6, 10.4, STEEL]], tubes=cols,
       note="The Neue Nationalgalerie (Mies van der Rohe, 1968): the black steel roof plate on eight columns over the "
            "dark glass hall\n(its LoD2 hall and the plate's four overhang canopies excluded in [buildings]: a beige hollow box)")

# ------------------------------------------------------------------ Checkpoint Charlie
# the replica booth (1998 copy of the 1961-ish Allied hut) on the Friedrichstraße's centre line facing south (the
# American sector), about 3.6 m along the street, 2.4 m across, 2.6 m to the eave with a flat roof; sandbags stacked
# 1.1 m high round its front and sides; the sign on its two posts ~15 m south of it, white with black lettering (three
# lines: English, Russian, French and German), 3.5 m up, read by those driving north
cc = utm(13.390381, 52.507432)
WHITE, SAND, BOARD = "#eeeeea", "#a89a78", "#f2f2ee"
figure("Checkpoint Charlie booth", cc, 0.0, WHITE, 3.0, variant=0.5,
       boxes=[[0, 1.3, 0, 2.4, 2.6, 3.6, WHITE], [0, 2.75, 0, 2.9, 0.3, 4.1, "#d8d8d2"],
              [0, 1.6, -1.81, 1.6, 1.0, 0.04, "#2a3038"], [1.21, 1.6, 0, 0.04, 1.0, 2.0, "#2a3038"],
              [-1.21, 1.6, 0, 0.04, 1.0, 2.0, "#2a3038"],
              [0, 0.55, -2.6, 3.6, 1.1, 0.9, SAND], [1.85, 0.55, -0.6, 0.9, 1.1, 3.4, SAND], [-1.85, 0.55, -0.6, 0.9, 1.1, 3.4, SAND]],
       tubes=[[[0.6, 2.9, 0.8], [0.6, 6.0, 0.8], 0.04, "#d8d8d2"]],
       note="Checkpoint Charlie: the replica booth, its sandbags and the sector sign (Friedrichstraße, OSM n417346627)")
sign = cc + frame_of(0.0)[1] * -15.0
figure("Checkpoint Charlie sign", sign, 0.0, BOARD, 5.2, variant=0.5,
       boxes=[[0, 4.3, 0, 3.4, 1.8, 0.12, BOARD], [0, 4.6, -0.07, 3.0, 0.25, 0.02, "#1c1c1c"],
              [0, 4.15, -0.07, 2.6, 0.16, 0.02, "#1c1c1c"], [0, 3.8, -0.07, 3.0, 0.16, 0.02, "#1c1c1c"]],
       tubes=[[[-1.4, 0.0, -0.1], [-1.4, 5.2, -0.1], 0.07, "#5a5d60"], [[1.4, 0.0, -0.1], [1.4, 5.2, -0.1], 0.07, "#5a5d60"]],
       note="Checkpoint Charlie's sign: \"You are leaving the American sector\" (on its two posts, its lettering facing south, to those driving north)")

# ------------------------------------------------------------------ the Soviet War Memorial (Treptower Park)
# the mound: OSM's grass ring round the mausoleum (60 m across) rising ~8 m; on it the round white mausoleum (OSM 9 m,
# ~12 m across, a frieze of mosaics inside); on that Vuchetich's 12 m bronze soldier, the child on his left arm, the
# lowered sword in his right hand, the broken swastika under his boots (the statue a few tubes, dark bronze); the
# whole 30 m (Wikipedia DE)
mz = osm_poly(142701713)
mc = np.array(mz.centroid.coords[0])
MOUND, PLINTH, BRONZE = "#56703a", "#d6d3ca", "#4a4c46"
figure("Soviet War Memorial mound", mc, 0.0, MOUND, 8.0, variant=0.5, segments=24,
       sections=[[0.0, 0, 0, 27.0, 27.0], [2.0, 0, 0, 22.0, 22.0], [5.5, 0, 0, 13.0, 13.0], [8.0, 0, 0, 7.5, 7.5]],
       note="The Soviet War Memorial in Treptower Park (Vuchetich and Belopolsky, 1949): the mound, the mausoleum and the soldier")
st = []
# legs, body, the arm with the child, the sword arm and the sword
for sd in (-1, 1):
    st.append([[sd * 0.9, 18.0, 0.2 * sd], [sd * 0.7, 22.6, 0.0], 0.75, BRONZE])
st += [[[0, 22.3, 0], [0, 27.6, 0.2], 1.5, BRONZE],              # the greatcoat and the chest
       [[0, 27.6, 0.2], [0, 29.2, 0.3], 0.62, BRONZE],           # the head
       [[-1.4, 26.8, 0.4], [-1.6, 25.2, 1.0], 0.5, BRONZE],      # the left arm holding the child
       [[-1.5, 25.0, 1.0], [-1.3, 27.0, 1.1], 0.6, BRONZE],      # the child
       [[1.4, 26.8, 0.2], [2.0, 24.6, 0.4], 0.45, BRONZE],       # the right arm
       [[2.0, 24.6, 0.4], [2.3, 19.2, 0.9], 0.16, BRONZE]]       # the lowered sword
gate = (np.array(osm_poly(142701792).centroid.coords[0]) + np.array(osm_poly(1002636043).centroid.coords[0])) / 2
figure("Soviet War Memorial soldier", mc, bearing(gate - mc), PLINTH, 29.2, variant=0.5,
       prisms=[[ring(6.2, 16), 8.0, 16.6, PLINTH], [ring(6.6, 16), 16.6, 17.2, PLINTH], [ring(2.6, 12), 17.2, 18.0, "#8a8c86"]],
       tubes=st, note="")
# the two lowered banners of red granite either side of the entrance from Puschkinallee, 14 m high (OSM), each tapering
# from its broad foot to the lowered tip; a kneeling soldier before each (a small dark block)
GRANITE = "#7c4339"
for wid in (142701792, 1002636043):
    g = osm_poly(wid)
    gc = np.array(g.centroid.coords[0])
    c2, u2, v2, L2_, W2 = rect(g)
    pts = [local(p, gc, bearing(u2)) for p in np.array(g.exterior.coords)[:-1]]
    figure(f"Soviet War Memorial banner {wid}", gc, bearing(u2), GRANITE, 14.0, variant=0.5,
           prisms=[[pts, 0.0, 1.4, "#8a8a84"], [pts, 1.4, 14.0, GRANITE, 0.25]],
           boxes=[[0, 1.4 + 1.3, -0.5 * L2_ - 2.0, 1.6, 2.6, 2.4, BRONZE]],
           note="")

# ------------------------------------------------------------------ the Alte Nationalgalerie's temple front
# Stüler's Corinthian temple on its high podium (Wikipedia DE: "Tempel auf hohem Sockel"): at the south end eight
# columns across the front over the podium's ~10 m, the entablature and a pediment to ~27 m, the double stair (the
# Freitreppe) climbing to it from the Kolonnadenhof; warm sandstone (#cdb48f, the row's tint)
an = piece("DEBE01YYK00000rL")
c, u, v, Ln, Wd = rect(an.geometry)
fwd = u if u[1] < 0 else -u                          # forward: the short south end
pc = c + fwd * (Ln / 2 + 0.5)
SST, SST2 = "#d2bb95", "#c2aa86"
half = Wd / 2 - 2.0
cols = [[[round(float(x), 2), 10.4, 2.0], [round(float(x), 2), 22.0, 2.0], 0.62, SST] for x in np.linspace(-half + 1.0, half - 1.0, 8)]
figure("Alte Nationalgalerie temple front", pc, bearing(fwd), SST, 27.5, variant=0.4, tubes=cols,
       boxes=[[0, 5.2, 1.5, Wd, 10.4, 5.0, SST2], [0, 23.0, 1.6, Wd - 1.0, 2.0, 4.6, SST],
              [-Wd / 4, 2.6, 7.0, Wd / 2 - 2.0, 5.2, 8.0, SST2], [Wd / 4, 2.6, 7.0, Wd / 2 - 2.0, 5.2, 8.0, SST2],
              [0, 7.6, 6.0, Wd * 0.35, 5.2, 6.0, SST2]],
       slabs=[[[[-Wd / 2 + 0.5, 24.0], [Wd / 2 - 0.5, 24.0], [0.0, 28.0]], -0.7, 3.9, SST]],
       note="The Alte Nationalgalerie (Stüler and Strack, 1876): the Corinthian temple front on its high podium, the double stair")

# ------------------------------------------------------------------ the Berlin Wall at the Bernauer Straße memorial
# the preserved and rebuilt stretches by the Ackerstraße (OSM barrier=wall historic=wall, 3.6 m): the L-shaped
# "Stützwandelement UL 12.41" slabs, pale weathered concrete, the round pipe on top; one figure per straight piece
WALL, PIPE = "#bdb9ae", "#c9c6bc"
for wid in (1504490305, 1504490306, 1504490315, 1504490317, 1504490318):
    pts = osm_line(wid)
    for k, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
        d = b - a
        ln = float(np.hypot(*d))
        if ln < 1.0:
            continue
        figure(f"Berlin Wall w{wid}", (a + b) / 2, bearing(d / ln), WALL, 3.6, variant=0.5,
               boxes=[[0, 1.6, 0, 0.25, 3.2, ln, WALL], [0.5, 0.15, 0, 1.2, 0.3, ln, WALL]],
               tubes=[[[0, 3.35, -ln / 2], [0, 3.35, ln / 2], 0.3, PIPE]],
               note="The Berlin Wall at the Gedenkstätte Berliner Mauer (Bernauer Straße): the preserved and rebuilt segments (OSM)"
               if wid == 1504490305 and k == 0 else None)

# ------------------------------------------------------------------ write the generated include file
out = HERE / "generated" / "structures-m10f.toml"
out.parent.mkdir(exist_ok=True)
out.write_text("# Generated by scripts/m10f_structures.py: do not edit (edit the script and run it again).\n"
               "# city.toml's `include` list lays this file under its own settings; the [[structures]] below are\n"
               "# in the order the script builds them.\n" + "\n".join(blocks))
print(f"{len(blocks)} structures written to {out}")
