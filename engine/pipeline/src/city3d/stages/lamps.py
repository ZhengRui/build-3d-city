"""06e_lamps: real street lamps for the viewer's night, from a city's public lighting inventory (city.toml
[lamps] path: a GeoJSON of points, WGS84; Paris: the Ville de Paris "Eclairage public", 165,581 lamps).

Off unless [lamps] path is set: without it the viewer's street light stays the procedural posts along every
kerb (ground.js). With it, inside the inventory's coverage the viewer draws each real lamp instead: a pool of
light on the street under it, of its real height and colour temperature (sodium where the inventory says so),
and the lamp head's own glow; the procedural posts stay only outside the coverage (lamps.js).

Kept: open-air lamps (the categories in [lamps] skip_categories are dropped: tunnels) of the fixture kinds in
[lamps] kinds, each with the height of its support where the inventory has one, else its kind's default
(kinds). Colour: the lamp's colour temperature (K), low-pressure sodium flagged apart (monochrome orange);
brightness: the lamp's flux (lm), else its power times its family's efficacy (lm/W).

Where it stands: on the ground (05a_terrain) or, within a deck's width of an elevated road (roads.gpkg's 3D
ways), on that deck, at the markings layer's height. Its pool's radius (2 x its height at most) is cut where the
ground falls away by more than 1.5 m (quay walls over the river's banks and the water), so no pool hangs in
the air.

Output, lamps/ in the data folder (web/lamps links to it):
  lamps.json   origin, count, chunk size, chunks [{x, z (scene centre), n, offset (records)}], the coverage
               mask's grid (x0, z0, cell, nx, nz) and the kinds' tallies
  lamps.bin    gzip of 10-byte records, chunk by chunk: int16 x, z (dm from the chunk's centre), int16 y
               (dm, scene), u8 height (dm above the street, up to 25.5 m), u8 pool radius (dm/2: up to 51 m),
               u8 colour (K / 100; 1 = low-pressure sodium, 2 = a gas mantle), u8 flux (100 lm)
  mask.bin     u8 nx x nz, row by row from the north-west: 255 where the inventory covers the streets (a lamp
               within ~100 m), blurred at its edge; the viewer's procedural posts are dimmed by it
"""
import gzip
import json
import math
from collections import Counter, defaultdict

import geopandas as gpd
import numpy as np
import shapely
from pyproj import Transformer

from ..common import CFG, DATA, RAW, UTM, Terrain, link_web
from . import markings as mk

LC = CFG.get("lamps", {})
OUT = DATA / "lamps"
CHUNK = 2000.0
MASK_CELL = 50.0
Y_LIFT = mk.ROAD_Y + mk.OVER_Y + 0.06       # the markings layer, a little above it
# lumens per watt by lamp family (roughly, ballast included)
EFFICACY = [("led", 110), ("basse pression", 140), ("haute pression", 95), ("sodium", 95), ("iodure", 85),
            ("cosmopolis", 100), ("fluo", 60), ("tube", 70), ("induction", 70)]


def features(path):
    """Stream the features of a big one-line GeoJSON without holding it: split on each feature's start."""
    start = '{"type":"Feature"'
    buf = ""
    with open(path, "r", encoding="utf-8") as f:
        while True:
            chunk = f.read(1 << 22)
            if not chunk:
                break
            buf += chunk
            parts = buf.split(start)
            buf = parts.pop()
            for p in parts:
                p = p.rstrip().rstrip(",")
                if p.startswith(','):            # (',"geometry"...' or ',"id":...,"geometry"...'; not the header)
                    yield json.loads(start + p)
        buf = buf.rstrip()
        if buf.endswith("]}"):
            buf = buf[:-2].rstrip()
        if buf.startswith(','):
            yield json.loads(start + buf)


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def main():
    path = LC.get("path", "")
    if not path and LC.get("generate"):
        e, n, h, code, lm, tally = generated()
        return write(e, n, h, code, lm, tally)
    if not path:
        print("06e_lamps: no [lamps] path in city.toml: the viewer keeps its procedural street lamps")
        return
    kinds = LC.get("kinds", {})
    skip = set(LC.get("skip_categories", []))
    skip_status = tuple(LC.get("skip_status", []))
    contains = LC.get("kind_match", "prefix") == "contains"
    f = LC.get("fields", {})
    F_KIND, F_CAT, F_H, F_K, F_FAM, F_W, F_LM = (f.get(k) for k in ("kind", "category", "height", "kelvin", "family", "power", "flux"))
    F_STATUS, F_STREET = f.get("status"), f.get("street")
    to_utm = Transformer.from_crs(LC.get("crs", "EPSG:4326"), UTM, always_xy=True)
    rows, tally, dropped, colours = [], Counter(), Counter(), Counter()
    for feat in features(RAW / path):
        p = feat["properties"]
        kind = (p.get(F_KIND) or "").strip()
        if p.get(F_CAT) in skip:
            dropped["category " + str(p.get(F_CAT))] += 1
            continue
        if F_STATUS and skip_status and str(p.get(F_STATUS) or "").startswith(skip_status):
            dropped["status " + str(p.get(F_STATUS))] += 1
            continue
        kl = kind.lower()
        key = next((k for k in kinds if (k.lower() in kl if contains else kl.startswith(k.lower()))), None)
        if key is None or feat.get("geometry") is None:
            dropped["kind " + kind] += 1
            continue
        g = feat["geometry"]
        lon, lat = (g["coordinates"][0] if g["type"] == "MultiPoint" else g["coordinates"])[:2]
        spec = kinds[key]
        # a kind: [default height, min, max], or a table { h, min, max, kelvin, flux, heads, gas, sodium }:
        # its own colour temperature and flux (an inventory without them per lamp: Berlin), `heads` lamps on
        # one post (double or triple brackets: the flux times that), `gas` a gas mantle (green-gold, code 2),
        # `sodium` the share of streets (whole streets, by fields.street) whose lamps of this kind are high-pressure sodium
        if isinstance(spec, dict):
            dh, hmin, hmax = spec["h"], spec.get("min", spec["h"]), spec.get("max", spec["h"])
        else:
            dh, hmin, hmax = spec
            spec = {}
        h = num(p.get(F_H))
        h = dh if h is None or h < hmin or h > hmax else h
        fam = (p.get(F_FAM) or "").lower()
        k = num(p.get(F_K)) or spec.get("kelvin")
        lps = "basse pression" in fam
        code = 1 if lps else int(round((k if k and 1500 <= k <= 7000 else 3000) / 100))
        if spec.get("gas"):
            code = 2
        elif spec.get("sodium") and _hash(p.get(F_STREET) or "", "sodium") < spec["sodium"]:
            code = 20
        w = num(p.get(F_W)) or 0
        eff = next((e for n, e in EFFICACY if n in fam), 80)
        lm = num(p.get(F_LM)) if F_LM else None
        if lm is None or not 200 <= lm <= 60000:
            lm = spec.get("flux") or (w * eff if 5 <= w <= 1000 else 3500)
        lm = min(lm * spec.get("heads", 1), 25500)
        rows.append((lon, lat, h, code, lm))
        tally[key] += 1
        colours["gas" if code == 2 else "sodium" if code in (1, 20) else f"{code * 100} K"] += 1
    print(f"{len(rows):,} lamps kept: {dict(tally)}; dropped: {dict(dropped.most_common(8))}; colours {dict(colours)}")
    a = np.array(rows, np.float64)
    e, n = to_utm.transform(a[:, 0], a[:, 1])
    clip = LC.get("clip", -1)
    if clip is not None and clip >= 0:
        # only lamps within `clip` m of the boundary: an inventory pulled for a box much larger than the area
        # (Berlin: 110,609 lamps, three quarters in the town ring) cost the night overview ~24 ms on the Iris Xe;
        # past it the ground's procedural town lamps (ground.outerLamps) take over at the mask's soft edge
        from ..common import boundary
        area = boundary().to_crs(UTM).union_all().buffer(float(clip))
        keep = shapely.contains_xy(area, e, n)
        print(f"{keep.sum():,} lamps within {float(clip):.0f} m of the boundary ({(~keep).sum():,} beyond dropped)")
        a, e, n = a[keep], e[keep], n[keep]
    write(e, n, a[:, 2], a[:, 3], a[:, 4], tally)


def write(e, n, h, code, lm, tally):
    """Stand the lamps (UTM e, n; height m, colour code, flux lm) on the ground or their deck, cut their pools
    where the ground falls away, and write lamps/ (see the module's docstring)."""
    a = np.column_stack([np.asarray(h, np.float64), np.asarray(h, np.float64), np.asarray(h, np.float64),
                         np.asarray(code, np.float64), np.asarray(lm, np.float64)])
    terrain = Terrain()
    x, z = terrain.to_scene(e, n)
    ground = terrain.height(x, z)
    y = ground.copy()

    # on decks: within a deck's half-width (+2 m) of an elevated road, its height there
    ways = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    ways = ways[ways.elevated & (ways.kind != "rail")].reset_index(drop=True)
    on_deck = np.zeros(len(a), bool)
    if len(ways):
        lines = ways.geometry.values
        tree = shapely.STRtree(shapely.buffer(lines, ways.width.values / 2 + 2, cap_style="flat"))
        pts = shapely.points(np.column_stack([e, n]))
        li, wi = tree.query(pts, predicate="within")
        best = {}
        for i, j in zip(li, wi):
            g = lines[j]
            d = g.project(pts[i])
            zz = g.interpolate(d).z if g.has_z else None
            if zz is None or not math.isfinite(zz):
                continue
            if zz > ground[i] + 2 and (i not in best or zz > best[i]):
                best[i] = zz
        for i, zz in best.items():
            y[i] = zz
            on_deck[i] = True
    print(f"{on_deck.sum():,} lamps on bridge decks and viaducts")

    # pool radius: 2 x the height, cut where the ground falls away (quays over the banks, the river)
    h = a[:, 2]
    r = np.minimum(2 * h, 24.0)
    for ang in np.arange(8) * np.pi / 4:
        for frac in (0.35, 0.6, 0.8, 1.0):
            rr = r * frac
            gx, gz = x + np.cos(ang) * rr, z + np.sin(ang) * rr
            drop = (y - terrain.height(gx, gz)) > 1.5
            if on_deck.any():
                drop &= ~on_deck              # (decks: the pool spills over the parapet into the air; kept small)
            r = np.where(drop, np.minimum(r, rr * 0.8), r)
    r[on_deck] = np.minimum(r[on_deck], 9.0)
    y = y + Y_LIFT

    # chunks
    cx, cz = np.floor(x / CHUNK).astype(int), np.floor(z / CHUNK).astype(int)
    order = np.lexsort((cx, cz))
    rec = np.zeros(len(a), dtype=[("x", "<i2"), ("z", "<i2"), ("y", "<i2"), ("h", "u1"), ("r", "u1"), ("c", "u1"), ("f", "u1")])
    chunks = []
    groups = defaultdict(list)
    for i in order:
        groups[(cx[i], cz[i])].append(i)
    off = 0
    parts = []
    for (i0, k0), idx in sorted(groups.items(), key=lambda t: (t[0][1], t[0][0])):
        idx = np.array(idx)
        mx, mz = (i0 + 0.5) * CHUNK, (k0 + 0.5) * CHUNK
        rr = np.zeros(len(idx), dtype=rec.dtype)
        rr["x"] = np.round((x[idx] - mx) * 10)
        rr["z"] = np.round((z[idx] - mz) * 10)
        rr["y"] = np.round(y[idx] * 10)
        rr["h"] = np.clip(np.round(h[idx] * 10), 1, 255)
        rr["r"] = np.clip(np.round(r[idx] * 5), 4, 255)
        rr["c"] = a[idx, 3]
        rr["f"] = np.clip(np.round(a[idx, 4] / 100), 1, 255)
        parts.append(rr)
        chunks.append({"x": mx, "z": mz, "n": int(len(idx)), "offset": off})
        off += len(idx)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "lamps.bin").write_bytes(gzip.compress(np.concatenate(parts).tobytes(), 9))

    # coverage mask: cells with a lamp, grown by 2 cells, softened at the edge
    x0, z0 = math.floor((x.min() - 300) / MASK_CELL) * MASK_CELL, math.floor((z.min() - 300) / MASK_CELL) * MASK_CELL
    nx = int(math.ceil((x.max() + 300 - x0) / MASK_CELL)); nz = int(math.ceil((z.max() + 300 - z0) / MASK_CELL))
    m = np.zeros((nz, nx), np.float32)
    m[((z - z0) // MASK_CELL).astype(int), ((x - x0) // MASK_CELL).astype(int)] = 1
    for _ in range(2):
        g = m.copy()
        g[1:] = np.maximum(g[1:], m[:-1]); g[:-1] = np.maximum(g[:-1], m[1:])
        g[:, 1:] = np.maximum(g[:, 1:], m[:, :-1]); g[:, :-1] = np.maximum(g[:, :-1], m[:, 1:])
        m = g
    b = m.copy()
    b[1:-1, 1:-1] = sum(m[1 + dz:m.shape[0] - 1 + dz, 1 + dx:m.shape[1] - 1 + dx] for dz in (-1, 0, 1) for dx in (-1, 0, 1)) / 9
    (OUT / "mask.bin").write_bytes(np.round(b * 255).astype(np.uint8).tobytes())
    index = {"origin": list(terrain.origin), "count": int(len(a)), "chunk": CHUNK, "chunks": chunks,
             "mask": {"x0": x0, "z0": z0, "cell": MASK_CELL, "nx": nx, "nz": nz},
             "kinds": dict(tally), "onDeck": int(on_deck.sum()),
             "source": LC.get("label", LC.get("path", ""))}
    (OUT / "lamps.json").write_text(json.dumps(index, indent=1))
    kb = (OUT / "lamps.bin").stat().st_size / 1024
    print(f"lamps.bin {kb:.0f} KB gzip, {len(chunks)} chunks; mask {nx} x {nz} ({MASK_CELL:.0f} m); "
          f"heights median {np.median(h):.1f} m, pool radius median {np.median(r):.1f} m")
    link_web("lamps")


# ---- generated lamps: a city without a lighting inventory ([lamps] generate = true; London) ----------------------
# Posts along roads.gpkg's ways at the spacing and layout of their class ([lamps.classes], by OSM highway, else
# the way's kind): `spacing` m from one post to the next along the road, "staggered" (alternate kerbs), "opposite"
# (pairs facing) or "one" (one kerb, chosen per street); at the kerb (half the way's width out, + 0.4 m). Colour temperature by area ([[lamps.
# areas]]: a district of boundary.gpkg or a lon/lat ring, later ones win; a kelvin per highway or kind, `*` the
# rest, and `heritage` for minor streets inside a conservation area of [lamps] conservation), a share of streets on
# sodium (whole streets, [lamps] sodium, outside areas with `sodium = false`), gas lamps ([[lamps.gas]] circles: a
# share of the minor streets' lamps there, 2,000 K, low and dim; and OSM highway=street_lamp nodes tagged gas),
# and rows of special lamps along named roads ([[lamps.rows]]: the Victoria Embankment's dolphin lamps, on the
# river side). Lamps closer than [lamps] dedupe m to one already placed (junctions, twin carriageways) are dropped,
# the bigger road's kept.

def _lonlat_to_utm():
    return Transformer.from_crs("EPSG:4326", UTM, always_xy=True)


def _along(line, step, phase):
    """Points (x, y) and unit tangents every `step` m along a line, starting `phase` m in."""
    L = line.length
    if L < 1:
        return np.zeros((0, 2)), np.zeros((0, 2))
    d = np.arange(phase % step, L, step)
    if not len(d) and L > step / 3:
        d = np.array([L / 2])
    pts = shapely.line_interpolate_point(line, d)
    p = shapely.get_coordinates(pts)[:, :2]
    q = shapely.get_coordinates(shapely.line_interpolate_point(line, np.minimum(d + 1.0, L)))[:, :2]
    r = shapely.get_coordinates(shapely.line_interpolate_point(line, np.maximum(d - 1.0, 0)))[:, :2]
    t = q - r
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-6)
    return p, t


def _hash(*v):
    h = 2166136261
    for x in v:
        for ch in str(x):
            h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h / 0xFFFFFFFF


def _osm_lamps():
    """OSM's highway=street_lamp nodes in the scene (cached in the data folder): [(lon, lat, tags)]."""
    from ..common import overpass, boundary
    f = DATA / "osm_street_lamps.json"
    if not f.exists():
        b = boundary().to_crs("EPSG:4326").total_bounds
        res = overpass(f"[out:json][timeout:300][bbox:{b[1]:.5f},{b[0]:.5f},{b[3]:.5f},{b[2]:.5f}];"
                       "node[highway=street_lamp];out;")
        f.write_text(json.dumps([(el["lon"], el["lat"], el.get("tags", {})) for el in res["elements"]]))
    return json.loads(f.read_text())


def generated():
    from ..common import districts
    classes = LC.get("classes", {})
    ways = gpd.read_file(DATA / "roads.gpkg", layer="ways").to_crs(UTM)
    ways = ways[ways.kind != "rail"].reset_index(drop=True)
    to_utm = _lonlat_to_utm()
    E, N, H, K, LM, PRI, CLS, WAY = [], [], [], [], [], [], [], []
    tally = Counter()
    for i, w in enumerate(ways.itertuples()):
        c = classes.get(w.highway) or classes.get(w.kind)
        if not c or w.geometry is None:
            continue
        key = w.highway if w.highway in classes else w.kind
        if _hash(w.osm_id, "share") > c.get("share", 1.0):
            continue
        sp = float(c["spacing"])
        layout = c.get("layout", "one")
        half = float(w.width) / 2 + 0.4
        lines = list(getattr(w.geometry, "geoms", [w.geometry]))
        for li, line in enumerate(lines):
            line = shapely.force_2d(line)
            ph = _hash(w.osm_id, li) * sp
            if layout == "staggered":
                p, t = _along(line, sp, ph)
                side = np.where(np.arange(len(p)) % 2 == 0, 1.0, -1.0)
            elif layout == "opposite":
                p0, t0 = _along(line, sp, ph)
                p, t = np.vstack([p0, p0]), np.vstack([t0, t0])
                side = np.r_[np.ones(len(p0)), -np.ones(len(p0))]
            else:
                p, t = _along(line, sp, ph)
                side = np.full(len(p), 1.0 if _hash(w.osm_id, "side") < 0.5 else -1.0)
            if not len(p):
                continue
            nrm = np.column_stack([-t[:, 1], t[:, 0]]) * side[:, None] * half
            q = p + nrm
            E.append(q[:, 0]); N.append(q[:, 1])
            m = len(q)
            H.append(np.full(m, float(c.get("h", 8.0)))); LM.append(np.full(m, float(c.get("flux", 6000))))
            K.append(np.full(m, float(c.get("kelvin", 3000)))); PRI.append(np.full(m, float(c.get("priority", 0))))
            CLS.append(np.full(m, key, dtype=object)); WAY.append(np.full(m, i))
    e, n = np.concatenate(E), np.concatenate(N)
    h, kel, lm = np.concatenate(H), np.concatenate(K), np.concatenate(LM)
    pri, cls, way = np.concatenate(PRI), np.concatenate(CLS), np.concatenate(WAY)
    kind_of = ways.kind.values[way]
    print(f"{len(e):,} posts along {len(ways):,} ways")

    # colour by area (later areas win)
    pts = shapely.points(np.column_stack([e, n]))
    dist = districts()
    default_sodium = float(LC.get("sodium", 0.0))
    sod_ok = np.ones(len(e), bool)
    heritage = np.zeros(len(e), bool)
    cons = None
    if LC.get("conservation"):
        b = dist.to_crs("EPSG:4326").total_bounds
        ca = gpd.read_file(RAW / LC["conservation"], bbox=tuple(b)).to_crs(UTM)
        cons = shapely.STRtree(ca.geometry.values)
        li, _ = cons.query(pts, predicate="within")
        heritage[np.unique(li)] = True
    print(f"{heritage.sum():,} posts in conservation areas")
    for ar in LC.get("areas", []):
        if "district" in ar:
            g = dist[dist.name == ar["district"]].union_all()
        else:
            xs, ys = to_utm.transform(*np.array(ar["ring"], float).T)
            g = shapely.Polygon(np.column_stack([xs, ys]))
        inside = shapely.contains(g, pts)
        kk = ar.get("kelvin", {})
        for j in np.flatnonzero(inside):
            v = kk.get(cls[j]) or kk.get(kind_of[j]) or kk.get("*")
            if heritage[j] and ar.get("heritage") and kind_of[j] != "major":
                v = ar["heritage"]
            if v:
                kel[j] = v
        if ar.get("sodium") is False:
            sod_ok &= ~inside
        tally["area " + ar.get("district", ar.get("name", "ring"))] += int(inside.sum())
    # sodium: whole streets
    wsod = np.array([_hash(ways.osm_id.values[k], ways.name.values[k] or "", "sodium") for k in way]) < default_sodium
    sod = wsod & sod_ok & (kind_of != "service")
    code = np.round(kel / 100)
    code[sod] = 20                          # high-pressure sodium: 2,000 K (low-pressure would be 1)
    tally["sodium"] = int(sod.sum())

    # gas lamps in circles: a share of the minor streets' posts, 2,000 K, 4 m, dim
    for gz in LC.get("gas", []):
        gx, gy = to_utm.transform(*gz["at"])
        near = (np.hypot(e - gx, n - gy) < gz["r"]) & (kind_of != "major")
        pick = near & (np.array([_hash(round(a), round(b), "gas") for a, b in zip(e, n)]) < gz.get("share", 1.0))
        code[pick] = 20; h[pick] = 4.0; lm[pick] = gz.get("flux", 1200); pri[pick] = 5
        tally["gas (areas)"] += int(pick.sum())

    extra = []                              # (e, n, h, code, lm, priority)
    # OSM's own special lamps: gas
    if LC.get("osm_gas", False):
        for lon, lat, t in _osm_lamps():
            lt = (t.get("lamp_type", "") + " " + t.get("light:method", "") + " " + t.get("lamp_mount", "")).lower()
            if "gas" in lt:
                x, y = to_utm.transform(lon, lat)
                extra.append((x, y, 4.0, 20, 1200, 9))
                tally["gas (OSM)"] += 1
    # rows along named roads (the Victoria Embankment's dolphin lamps): on the water's side or both
    water = None
    for row in LC.get("rows", []):
        sel = ways[ways.name.fillna("").isin(row["names"])]
        if row.get("side", "water") == "water" and water is None:
            wg = gpd.read_file(DATA / "ground.gpkg", layer="water").to_crs(UTM)
            water = wg.union_all()
        drop = np.zeros(len(e), bool)
        for w in sel.itertuples():
            for li, line in enumerate(getattr(w.geometry, "geoms", [w.geometry])):
                line = shapely.force_2d(line)
                p, t = _along(line, row["spacing"], _hash(w.osm_id, li, "row") * row["spacing"])
                if not len(p):
                    continue
                off = float(w.width) / 2 + row.get("kerb", 1.2)
                nrm = np.column_stack([-t[:, 1], t[:, 0]]) * off
                if row.get("side", "water") == "water":
                    a1, a2 = shapely.points(p + nrm), shapely.points(p - nrm)
                    d1, d2 = shapely.distance(a1, water), shapely.distance(a2, water)
                    s1 = np.where(d1 < d2, 1.0, -1.0)
                    q = p + nrm * s1[:, None]
                    qs = [q[np.minimum(d1, d2) < row.get("near", 1e9)]]
                else:
                    qs = [p + nrm, p - nrm]
                for q in qs:
                    for x, y in q:
                        extra.append((x, y, row["h"], round(row["kelvin"] / 100), row["flux"], 10))
                        tally["row " + row.get("label", row["names"][0])] += 1
            # the ordinary posts of that road give way to the row
            if row.get("replace", True):
                drop |= way == w.Index
        keep = ~drop
        e, n, h, code, lm, pri, kind_of = e[keep], n[keep], h[keep], code[keep], lm[keep], pri[keep], kind_of[keep]
        way, cls = way[keep], cls[keep]
    if extra:
        x = np.array(extra, float)
        e, n, h = np.r_[x[:, 0], e], np.r_[x[:, 1], n], np.r_[x[:, 2], h]
        code, lm, pri = np.r_[x[:, 3], code], np.r_[x[:, 4], lm], np.r_[x[:, 5], pri]
    # dedupe: the higher priority (then the bigger flux) first, a lamp within `dedupe` m of a kept one dropped
    from scipy.spatial import cKDTree
    order = np.lexsort((-lm, -pri))
    tree = cKDTree(np.column_stack([e, n]))
    taken = np.zeros(len(e), bool)
    gone = np.zeros(len(e), bool)
    r = float(LC.get("dedupe", 8.0))
    for i in order:
        if gone[i]:
            continue
        taken[i] = True
        for j in tree.query_ball_point((e[i], n[i]), r):
            if not taken[j]:
                gone[j] = True
    k = taken
    print(f"{k.sum():,} lamps after dropping {(~k).sum():,} within {r:.0f} m of another")
    kc = Counter(np.where(code[k] == 20, "2000 K", (code[k] * 100).astype(int).astype(str) + " K"))
    tally.update({"K " + a: b for a, b in kc.items()})
    return e[k], n[k], h[k], code[k], lm[k], tally


if __name__ == "__main__":
    main()
