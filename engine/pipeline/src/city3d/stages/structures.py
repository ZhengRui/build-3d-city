"""Structures the building table can't make: parametric models of a city's landmark structures, from city.toml
[[structures]] entries, built into the tiles by 06_tiles (their solid parts into the buildings mesh with a
facade style and tint, their cables into the bridge mesh). Two kinds:

  suspension  a suspension bridge's towers and main cables:
                towers   [[lon, lat], [lon, lat]]  the two tower centres (the axis runs through them)
                tower    {width across, depth along, height, deck (the roadway's level through the tower),
                          pier (masonry pier top under steel columns; 0: the tower is solid from the water),
                          arches (openings over the roadways), arch_width, arch_height, pilaster
                          (masonry: buttresses up each pier on the arch faces, projecting this far; a plinth),
                          columns (steel towers: offsets of the columns across; replaces arches),
                          column_width, column_depth (at the pier; tapering to column_top), bracing (lattice
                          between columns: [lo, hi] m), cap (top band's depth), portal_arch ([spring, crown]:
                          a round lattice arch over the roadway between the inner columns),
                          finials ([top, radius]: a post and a globe over each column),
                          open_legs (flange depth: columns as two flanges laced on their sides),
                          style, colour, pier_colour}
                cables   {across (offsets of the main cables), low (height at midspan), side (side span
                          length to the anchorages, or [first, second]), anchor (height at the anchorages), radius,
                          colour, deck and hangers (suspenders from the cable down to the deck height every
                          `hangers` m), stays {count, reach} (diagonal stays fanning down from each saddle to the
                          deck: the Brooklyn Bridge)}
                truss    stiffening trusses, one table or a list: {top (height of the top chord), depth, across
                          (offsets of the truss planes), panel (m, Warren diagonals), extent ("anchorages" or
                          "towers"), floors (heights of deck slabs between the outer planes: a double deck, a
                          promenade), width (member width), colour}
                roadways {centre, width}: 05b_roads moves the bridge's carriageways (the ways named for it in
                          [roads] decks) to +-centre m of the towers' line and gives them this width between the
                          anchorages, fading back to OSM's line beyond: OSM's needn't be symmetric about the towers
                          the trusses and cables are built on (the Brooklyn Bridge's promenade stood over one)
                side_piers  the side spans stand on piers: no suspenders there, straight backstays (Williamsburg)
                tower.portal_bay  bays wider than this (m) are braced only near the top (the portal over the
                          roadway); default 12
                towers may instead be "shores": the two tower sites are found where the bridge's deck (the
                roads with span = name, 05b_roads) leaves the land, `offshore` metres out into the water
  truss       a truss or arch bridge over the water between the shores its deck crosses (span = name): two
              lattice walls along its axis, piers at the shores; {width, deck, low (top of the trusses at mid
              channel), peak (over the piers; an arch: at mid channel), shape ("cantilever" or "arch"),
              style, colour, pier_colour, piers [[lon, lat], ...] (pier sites instead of the shores),
              anchors [[lon, lat], [lon, lat]] (the anchor arms' ends), pier_size [across, along],
              pier_towers {height, spire, width, depth} (posts and spires over the piers: the Queensboro),
              rib [spring, crown] (an arch's lower chord: a two-hinged arch, the deck hung from it),
              tower {height, across, along} (an arch's stone towers, from the water)}
  figure      a statue as lofted sections and tubes, in its own frame (x right, z forward, y up from its
              base), turned to face `facing` (compass degrees):
                at [lon, lat], base (height of its base over the ground), facing, colour, style, variant,
                sections [[y, x, z, rx, rz], ...] (ellipses bottom to top, one loft),
                tubes [[[x, y, z], [x, y, z], radius, colour?], ...], boxes [[x, y, z, sx, sy, sz, colour?], ...],
                prisms [[[[x, z], ...], y0, y1, colour?, scale?], ...] (an outline, convex or not, extruded from y0
                to y1: 30 Hudson Yards' triangular Edge deck; `scale` shrinks the top about the outline's mean point:
                a frustum, 0 a pyramid: Tower Bridge's roofs); sections may be left out (a figure of prisms/boxes)
                wedges [[[[x, z, top], ...], y0, colour?], ...]: a prism from y0 up to its own top at each outline
                  point (a sloped or curved roof over any outline, flat-shaded per triangle: the Bank of China
                  Tower's sloped prisms, a wing roof)
                slabs [[[[x, y], ...], z0, z1, colour?, scale?], ...]: the same with the outline drawn in the
                  figure's elevation (x right, y up) and extruded along z, front to back: a tower's body with an
                  arch through it, a pediment, a gable
                segments: the sections' loft resolution (default 16; a dome: 32)
                walls: true gives the prisms' and slabs' faces wall runs, so a windowed style (monument) draws its
                  bays on them (default: none, the faces plain as the style's solid colour)
                model {file (a mesh, glb/obj/stl, under the data folder), cut (model units along `up` below which
                  it is dropped: a scan's own pedestal), up and front (its axes, e.g. "+z" and "-y"), height (m
                  from the cut to its top), triangles (budget, meshoptimizer's simplifier), tip [m, colour] (the
                  top m metres in another colour: a gilded flame), credit (shown nowhere, for the README)}:
                  a scanned or modelled statue in place of the lofted sections
                top (m): the height the facade shader takes as the figure's top (default: its sections' top)
                glazing [{grid [[[x, y, z], ...], ...] (m rows of n points in the frame), period [pu, pv] (m: the
                  members' spacing along the rows and down the columns), colour (the members; fabric: the sheet),
                  kind "glass" (default) or "fabric"}, ...]: see-through sheets drawn into the tile's lattice mesh
                  (viewer/lattice.js kinds 3 and 4): a glass dome or barrel vault as a grid of light members over
                  panes that let most of the light through (the Reichstag's dome, Berlin Hbf's hall), a tent's
                  translucent membrane on thin cables (the Sony Center); no shadow; default none
  lattice_tower  an open iron lattice tower on four legs (the Eiffel Tower), in a figure's frame (x right, z
              forward, y up; its faces look along x and z): the members that make its outline are solid bars in
              the buildings mesh, the lattice between them is flat panels in the tile's `lattice` mesh, which the
              viewer draws with a cut-out pattern (viewer/lattice.js: the sky shows through; box-filtered, so it
              fades to the lattice's mean density with distance instead of shimmering):
                at, base, facing, height (its top, m), style (default floodlit), variant,
                colours [[y, "#hex"], ...] (the paint by height: three shades of Eiffel brown),
                legs [{profile [[y, outer, inner], ...], chord}, ...]: sections of the four legs at the corners of
                  a square, each leg a box from `inner` to `outer` half-width in x and in z (PCHIP through the
                  rows); its four edges are bars (chord: their width as a share of the leg's width), its faces
                  braced panels; a second section may start where the first ends (the legs above a deck)
                faces [[y0, y1], ...]: braced panels across each face between the legs (the shaft above a deck)
                arches {spring (height where the arch meets the legs' inner edges), crown (its intrados), rib,
                  depth, inset (behind the outer face), top (the spandrel lattice up to here)}: an arch on each face
                belts [[y0, y1, half, depth, colour?], ...]: solid girder rings (the decks' friezes)
                floors [[y, half, void, thick, colour?], ...]: deck slabs round a central void
                railings [[y0, y1, half], ...]: open railings round a deck (lattice bars)
                frustums [[y0, y1, half0, half1], ...]: braced square frustums (the campanile)
                boxes, tubes, prisms as a figure's (pavilions, the glazed top, the antennas)

Heights are over the water (MHW, the scene's 0) for bridges, over the ground for figures.
"""
import mapbox_earcut as earcut
import numpy as np
from shapely.geometry import Polygon

from ..common import CFG, UTM
from pyproj import Transformer

SPECS = CFG.get("structures", [])


def _lonlat(pts):
    to = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    return np.array([to.transform(lon, lat) for lon, lat in pts], dtype=float)


def _rect(c, u, v, a0, a1, b0, b1):
    """A rectangle in map coordinates: centre c, across unit u (a0..a1), along unit v (b0..b1)."""
    return Polygon([c + u * a0 + v * b0, c + u * a1 + v * b0, c + u * a1 + v * b1, c + u * a0 + v * b1])


def _tube(pts, radius, n=6):
    """A tube along a 3D polyline (scene x, y, z): pos, nrm, idx."""
    pts = np.asarray(pts, float)
    t = np.gradient(pts, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True).clip(1e-9)
    ref = np.where(np.abs(t[:, 1:2]) < 0.9, [[0, 1, 0]], [[1, 0, 0]])
    a = np.cross(t, ref)
    a /= np.linalg.norm(a, axis=1, keepdims=True)
    b = np.cross(t, a)
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.cos(ang)[None, :, None] * a[:, None] + np.sin(ang)[None, :, None] * b[:, None]
    pos = (pts[:, None] + radius * ring).reshape(-1, 3)
    nrm = ring.reshape(-1, 3)
    m = len(pts)
    i, j = np.meshgrid(np.arange(m - 1), np.arange(n), indexing="ij")
    p0, p1 = i * n + j, i * n + (j + 1) % n
    q0, q1 = p0 + n, p1 + n
    idx = np.stack([np.stack([p0, q0, p1], -1), np.stack([p1, q0, q1], -1)], 2).reshape(-1, 3)
    return pos, nrm, idx


def _loft(rings):
    """Closed loft through rings (list of (k, 3) arrays, same k), capped at the top: pos, nrm, idx."""
    rings = [np.asarray(r, float) for r in rings]
    k = len(rings[0])
    pos = np.concatenate(rings)
    idx = []
    for s in range(len(rings) - 1):
        for j in range(k):
            a, b = s * k + j, s * k + (j + 1) % k
            c, d = a + k, b + k
            idx += [[a, b, c], [b, d, c]]
    top = len(rings) - 1
    centre = len(pos)
    pos = np.vstack([pos, rings[-1].mean(0)])
    idx += [[top * k + j, top * k + (j + 1) % k, centre] for j in range(k)]
    idx = np.array(idx)
    # normals: area-weighted per vertex
    fn = np.cross(pos[idx[:, 1]] - pos[idx[:, 0]], pos[idx[:, 2]] - pos[idx[:, 0]])
    nrm = np.zeros_like(pos)
    for c in range(3):
        np.add.at(nrm, idx[:, c], fn)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True).clip(1e-9)
    return pos, nrm, idx


def span_axis(name):
    """(start, unit along, crossings along the axis) of the bridge whose deck ways carry span = name: the
    axis through their points (principal direction) and where it crosses from land to water or back."""
    import geopandas as gpd
    import shapely
    from ..common import DATA
    w = gpd.read_file(DATA / "roads.gpkg", layer="ways")
    w = w[(w["span"] == name) & w.elevated]
    xy = shapely.get_coordinates(w.geometry.values)
    c = xy.mean(0)
    _, _, vt = np.linalg.svd(xy - c, full_matrices=False)
    v = vt[0]
    t = (xy - c) @ v
    # centred on the main span: ramps curving off to one side at the ends pull the mean aside (the
    # Queensboro's by 38 m), so the median offset across of the middle half of the points
    u = np.array([v[1], -v[0]])
    mid = np.abs(t - np.median(t)) < 0.25 * (t.max() - t.min())
    c = c + u * np.median(((xy - c) @ u)[mid])
    a, b = c + v * t.min(), c + v * t.max()
    land = gpd.read_file(DATA / "ground.gpkg", layer="land").union_all()
    water = gpd.read_file(DATA / "ground.gpkg", layer="water").union_all()
    dry = land.difference(water)
    from shapely.geometry import LineString
    hit = LineString([a, b]).intersection(dry.boundary)
    pts = np.array([[p.x, p.y] for p in getattr(hit, "geoms", [hit]) if not p.is_empty and p.geom_type == "Point"])
    along = np.sort((pts - a) @ v) if len(pts) else np.array([])
    # crossings closer than 30 m (a pier's two sides) count once
    keep = [x for i, x in enumerate(along) if i == 0 or x - along[i - 1] > 30]
    return a, v, np.array(keep)


def beam(p0, p1, w, rgb, st, seed=0.3, d=None):
    """A box member between two scene points (x, y, z), w wide and d deep (square by default), in the
    buildings mesh's format (style st: plain or spire, no windows)."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    ax = p1 - p0
    L = np.linalg.norm(ax)
    if L < 1e-3:
        return None
    t = ax / L
    ref = np.array([0.0, 1.0, 0.0]) if abs(t[1]) < 0.95 else np.array([1.0, 0.0, 0.0])
    a = np.cross(t, ref)
    a /= np.linalg.norm(a)
    b = np.cross(t, a)
    d = w if d is None else d
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    pos, nrm, idx = [], [], []
    for k in range(4):
        (i0, j0), (i1, j1) = corners[k], corners[(k + 1) % 4]
        o0 = a * i0 * w / 2 + b * j0 * d / 2
        o1 = a * i1 * w / 2 + b * j1 * d / 2
        n = (o0 + o1)
        n /= np.linalg.norm(n)
        base = len(pos)
        pos += [p0 + o0, p0 + o1, p1 + o1, p1 + o0]
        nrm += [n] * 4
        idx += [[base, base + 1, base + 2], [base, base + 2, base + 3]]
    for end, sign in ((p0, -1), (p1, 1)):
        base = len(pos)
        pos += [end + a * i * w / 2 + b * j * d / 2 for i, j in corners]
        nrm += [t * sign] * 4
        idx += [[base, base + 1, base + 2], [base, base + 2, base + 3]]
    pos = np.array(pos)
    n = len(pos)
    return {"pos": pos, "nrm": np.array(nrm), "uv": np.zeros((n, 2)), "col": np.tile([*rgb[:3], 0.0], (n, 1)),
            "fac": np.tile([st + 0.999 * seed, max(p0[1], p1[1])], (n, 1)), "base": np.tile([0.0, 0.0], (n, 1)),
            "idx": np.array(idx).reshape(-1)}


def zones():
    """Where viaduct pillars must not stand: the suspended spans of [[structures]] suspension bridges, from
    anchorage to anchorage (their decks hang from the cables), as one polygon in UTM (or None)."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    out = []
    for spec in SPECS:
        if spec["kind"] != "suspension" or not spec.get("cables"):
            continue
        ends = _towers(spec)
        if ends is None:
            continue
        t0, t1, v, u = ends
        side = 0.0 if spec.get("side_piers") else spec["cables"]["side"]   # side spans on piers: the main span only
        out.append(LineString([t0 - v * side, t1 + v * side]).buffer(spec["tower"]["width"] / 2 + 8, cap_style="flat"))
    return unary_union(out) if out else None


def _towers(spec):
    if spec["towers"] == "shores":
        a, v, along = span_axis(spec["name"])
        if len(along) < 2:
            return None
        off = spec.get("offshore", 15.0)
        t0, t1 = a + v * (along[0] + off), a + v * (along[-1] - off)
    else:
        t0, t1 = _lonlat(spec["towers"])
    v = (t1 - t0) / np.linalg.norm(t1 - t0)
    return t0, t1, v, np.array([v[1], -v[0]])


def build(origin, terrain, extrude, style_id, srgb, to_scene):
    """(solids, cables, lattices): solids = [(map xy of the piece, building mesh)], cables = [(map xy, bridge
    mesh)], lattices = [(map xy, lattice mesh: pos, nrm, uv (pattern coordinates), col (rgb, pattern kind / 255),
    idx)]. extrude/style_id/srgb/to_scene are 06_tiles' own, passed in to keep one mesh format."""
    solids, cables, lattices = [], [], []
    for spec in SPECS:
        if spec["kind"] == "suspension":
            _suspension(spec, origin, terrain, extrude, style_id, srgb, to_scene, solids, cables)
        elif spec["kind"] == "truss":
            _truss(spec, origin, terrain, extrude, style_id, srgb, solids)
        elif spec["kind"] == "figure":
            _figure(spec, origin, terrain, style_id, srgb, to_scene, solids, lattices)
        elif spec["kind"] == "lattice_tower":
            _lattice_tower(spec, origin, terrain, style_id, srgb, to_scene, solids, lattices)
    if SPECS:
        print(f"structures: {len(SPECS)} ({len(solids)} solid pieces, {len(cables)} cables, "
              f"{len(lattices)} lattices)")
    return solids, cables, lattices


def _suspension(spec, origin, terrain, extrude, style_id, srgb, to_scene, solids, cables):
    T = spec["tower"]
    ends = _towers(spec)
    if ends is None:
        print(f"structures: {spec['name']}: its deck crosses no water; left out")
        return
    t0, t1, v, u = ends                                # v along the bridge, u across
    style = style_id[T.get("style", "plain")]
    rgb = srgb(T.get("colour", "#b0b0b0"))[0]
    pier_rgb = srgb(T.get("pier_colour", T.get("colour", "#b0b0b0")))[0]
    W, D, H = T["width"], T["depth"], T["height"]
    for n, c in enumerate((t0, t1)):
        g = float(terrain.height_utm([c[0]], [c[1]])[0])
        seed = T.get("variant", 0.37 + 0.2 * n)    # (floodlit towers: the floodlight's strength)
        add = lambda poly, top, base, col=rgb, st=style: solids.append(
            (c, extrude(poly, top, origin, col, (st, seed), base=base, ground=0.0, skirt=1.0 + g)))
        if T.get("columns"):
            # steel: a masonry pier, columns tapering upwards, lattice bracing between them, a cap
            pier = T.get("pier", 7.0)
            add(_rect(c, u, v, -W / 2 - 3, W / 2 + 3, -D / 2 - 5, D / 2 + 5), pier, 0.0, pier_rgb, style_id["plain"])
            cw, cd0, cd1 = T["column_width"], T["column_depth"], T.get("column_top", T["column_depth"] * 0.3)
            # open legs ([open_legs] = flange depth, m): each column is two flanges, front and back, laced by
            # X-bracing on its side faces, so the tower is a lattice seen from the side too (the GWB)
            fl = T.get("open_legs", 0.0)
            pieces = [(off, -cd0 / 2, cd0 / 2) for off in T["columns"]] if not fl else \
                [(off, b0, b1) for off in T["columns"] for b0, b1 in ((-cd0 / 2, -cd0 / 2 + fl), (cd0 / 2 - fl, cd0 / 2))]
            for off, b0, b1 in pieces:
                poly = _rect(c, u, v, off - cw / 2, off + cw / 2, b0, b1)
                m = extrude(poly, H, origin, rgb, (style, seed), base=pier, ground=0.0, skirt=0.0,
                            profile=None)
                # taper along the bridge only: squeeze the top ring's along-coordinates
                if m is not None:
                    p = m["pos"]
                    cs = to_scene(c[None], origin)[0]
                    rel = np.stack([p[:, 0] - cs[0], p[:, 2] - cs[1]], 1)
                    vs = np.array([v[0], -v[1]])
                    along = rel @ vs
                    f = np.clip((p[:, 1] - pier) / (H - pier), 0, 1)
                    k = 1 - f * (1 - cd1 / cd0)
                    rel2 = rel + (along * (k - 1))[:, None] * vs
                    p[:, 0], p[:, 2] = rel2[:, 0] + cs[0], rel2[:, 1] + cs[1]
                    solids.append((c, m))
            lat = T.get("bracing")
            offs = sorted(T["columns"])
            if fl:
                cs = to_scene(c[None], origin)[0]
                us, vs = np.array([u[0], -u[1]]), np.array([v[0], -v[1]])
                half = lambda y: (cd0 / 2 - fl / 2) * (1 - np.clip((y - pier) / (H - pier), 0, 1) * (1 - cd1 / cd0))
                tier = T.get("tier", 12.0)
                for off in offs:
                    for side in (-1, 1):
                        a_ = off + side * cw / 2
                        q = lambda y, sg: [cs[0] + us[0] * a_ + vs[0] * sg * half(y), y,
                                           cs[1] + us[1] * a_ + vs[1] * sg * half(y)]
                        for y0 in np.arange(pier, H - 0.1, tier):
                            y1 = min(y0 + tier, H)
                            for m in (beam(q(y0, -1), q(y1, 1), 0.6, rgb, style, seed=0.35),
                                      beam(q(y0, 1), q(y1, -1), 0.6, rgb, style, seed=0.35),
                                      beam(q(y1, -1), q(y1, 1), 0.8, rgb, style, seed=0.35)):
                                if m is not None:
                                    solids.append((c, m))
            if lat:
                # X-bracing between neighbouring columns in tiers, on both faces of the tower (open: the
                # sky shows through); the widest bay (the great arch over the roadway) only near the top
                tier = T.get("tier", 12.0)
                cs = to_scene(c[None], origin)[0]
                us = np.array([u[0], -u[1]])
                vs = np.array([v[0], -v[1]])
                for a0, a1 in zip(offs[:-1], offs[1:]):
                    ys = np.arange(lat[0], lat[1] - 0.1, tier)
                    if a1 - a0 > T.get("portal_bay", 12.0):
                        ys = ys[ys > lat[1] - 2.5 * tier]
                    for face in (-1, 1):
                        f = face * cd1 * 0.45
                        q = lambda aa, yy: [cs[0] + us[0] * aa + vs[0] * f, yy, cs[1] + us[1] * aa + vs[1] * f]
                        for y0 in ys:
                            y1 = min(y0 + tier, lat[1])
                            for m in (beam(q(a0, y0), q(a1, y1), 0.7, rgb, style, seed=0.35),
                                      beam(q(a1, y0), q(a0, y1), 0.7, rgb, style, seed=0.35),
                                      beam(q(a0, y1), q(a1, y1), 0.9, rgb, style, seed=0.35)):
                                if m is not None:
                                    solids.append((c, m))
            arch = T.get("portal_arch")
            if arch and lat:
                # the portal over the roadway: a round lattice arch between the inner columns, springing at
                # arch[0] and crowning at arch[1], with spandrel posts up to the top bracing (the GWB)
                cs = to_scene(c[None], origin)[0]
                us, vs = np.array([u[0], -u[1]]), np.array([v[0], -v[1]])
                mid_i = len(offs) // 2
                a0, a1 = offs[mid_i - 1], offs[mid_i]
                half, mid = (a1 - a0) / 2, (a0 + a1) / 2
                th = np.linspace(np.pi, 0, 13)
                for face in (-1, 1):
                    f = face * cd1 * 0.45
                    q = lambda aa, yy: [cs[0] + us[0] * aa + vs[0] * f, yy, cs[1] + us[1] * aa + vs[1] * f]
                    pts = [(mid + half * np.cos(t), arch[0] + (arch[1] - arch[0]) * np.sin(t)) for t in th]
                    for (x0_, y0_), (x1_, y1_) in zip(pts[:-1], pts[1:]):
                        m = beam(q(x0_, y0_), q(x1_, y1_), 1.4, rgb, style, seed=0.35)
                        if m is not None:
                            solids.append((c, m))
                    for x_, y_ in pts[2:-2:2]:
                        m = beam(q(x_, y_), q(x_, lat[1]), 0.6, rgb, style, seed=0.35)
                        if m is not None:
                            solids.append((c, m))
            cap = T.get("cap", 4.0)
            add(_rect(c, u, v, offs[0] - cw, offs[-1] + cw, -cd1 / 2 - 0.5, cd1 / 2 + 0.5), H, H - cap)
            fin = T.get("finials")
            if fin:
                # a post and a globe over each column ([top, radius]: the Manhattan Bridge's spheres at 106.7 m)
                cs = to_scene(c[None], origin)[0]
                us = np.array([u[0], -u[1]])
                top, r = fin
                for off in offs:
                    x_, z_ = cs + us * off
                    for m in (beam([x_, H, z_], [x_, top - 2 * r, z_], r * 0.5, rgb, style, seed=0.35),
                              beam([x_, top - 2 * r, z_], [x_, top, z_], r * 1.6, rgb, style, seed=0.35),
                              beam([x_, top - 1.6 * r, z_], [x_, top - 0.4 * r, z_], r * 2.0, rgb, style, seed=0.35)):
                        if m is not None:
                            solids.append((c, m))
        else:
            # masonry: solid to the roadway, piers between the arches up to their apex, a solid top
            deck, n_a, aw, ah = T["deck"], T.get("arches", 0), T.get("arch_width", 0.0), T.get("arch_height", 0.0)
            add(_rect(c, u, v, -W / 2, W / 2, -D / 2, D / 2), deck, 0.0)
            if n_a:
                lw = (W - n_a * aw) / (n_a + 1)
                # the openings' pointed tops: the piers step inwards over the arch's upper third
                steps = [(0.0, 0.0), (0.66, 0.12), (0.78, 0.26), (0.88, 0.4), (0.95, 0.47)]
                x = -W / 2
                for k in range(n_a + 1):
                    for j, (f0, grow) in enumerate(steps):
                        f1 = steps[j + 1][0] if j + 1 < len(steps) else 1.0
                        gl = aw * grow if k > 0 else 0.0            # into the opening on its left
                        gr = aw * grow if k < n_a else 0.0          # ... and on its right
                        add(_rect(c, u, v, x - gl, x + lw + gr, -D / 2, D / 2), deck + ah * f1, deck + ah * f0)
                    x += lw + aw
                add(_rect(c, u, v, -W / 2, W / 2, -D / 2, D / 2), H - 3.0, deck + ah)
                add(_rect(c, u, v, -W / 2 - 0.8, W / 2 + 0.8, -D / 2 - 0.8, D / 2 + 0.8), H, H - 3.0)     # cornice
                # the piers' buttresses: a pilaster up each pier on both arch faces, to under the cornice,
                # and the caisson's plinth at the water (T pilaster = projection, m; 0: none)
                pj = T.get("pilaster", 0.0)
                if pj:
                    x = -W / 2
                    for k in range(n_a + 1):
                        pw = lw * 0.55
                        mid = x + lw / 2
                        for face in (-1, 1):
                            b0, b1 = sorted((face * D / 2, face * (D / 2 + pj)))
                            add(_rect(c, u, v, mid - pw / 2, mid + pw / 2, b0, b1), H - 5.0, 0.0)
                        x += lw + aw
                    add(_rect(c, u, v, -W / 2 - 2.5, W / 2 + 2.5, -D / 2 - 2.5 - pj, D / 2 + 2.5 + pj), 5.0, 0.0,
                        pier_rgb, style_id["plain"])
            else:
                add(_rect(c, u, v, -W / 2, W / 2, -D / 2, D / 2), H, deck)
    A = spec.get("anchorage")
    if A:
        # the cables' anchorage blocks, side-span lengths beyond the towers (which: 0 beyond the first, 1 beyond
        # the second)
        sides = _sides(spec["cables"]["side"])
        for w in A.get("which", [0, 1]):
            c = t0 - v * (sides[0] + A["length"] / 2) if w == 0 else t1 + v * (sides[1] + A["length"] / 2)
            g = float(terrain.height_utm([c[0]], [c[1]])[0])
            solids.append((c, extrude(_rect(c, u, v, -A["width"] / 2, A["width"] / 2, -A["length"] / 2, A["length"] / 2),
                                      A["height"], origin, srgb(A.get("colour", T.get("colour", "#b0b0b0")))[0],
                                      (style_id["plain"], 0.4), ground=0.0, skirt=1.0 + g)))
    for TR in ([spec["truss"]] if isinstance(spec.get("truss"), dict) else spec.get("truss", [])):
        _stiffening(TR, t0, t1, v, u, _sides(spec["cables"]["side"]) if spec.get("cables") else (0, 0),
                    origin, to_scene, style_id, srgb, extrude, solids, T)
    C = spec.get("cables")
    if not C:
        return
    col = srgb(C.get("colour", "#8a8a86"))[0]
    span = np.linalg.norm(t1 - t0)
    sides = _sides(C["side"])
    sag = 0.0 if spec.get("side_piers") else 0.02         # backstays over piers run straight
    top = H - C.get("below_top", 2.0)
    for off in C["across"]:
        a0 = t0 - v * sides[0] + u * off
        a1 = t1 + v * sides[1] + u * off
        b0, b1 = t0 + u * off, t1 + u * off
        pts = []
        # side span: from the anchorage up to the saddle, sagging a little
        for s in np.linspace(0, 1, 16):
            xy = a0 + (b0 - a0) * s
            pts.append((*xy, C["anchor"] + (top - C["anchor"]) * s - 4 * sag * sides[0] * s * (1 - s)))
        for s in np.linspace(0, 1, 41)[1:]:
            xy = b0 + (b1 - b0) * s
            pts.append((*xy, top - (top - C["low"]) * 4 * s * (1 - s)))
        for s in np.linspace(0, 1, 16)[1:]:
            xy = b1 + (a1 - b1) * s
            pts.append((*xy, top + (C["anchor"] - top) * s - 4 * sag * sides[1] * s * (1 - s)))
        pts = np.array(pts)
        sc = to_scene(pts[:, :2], origin)
        p3 = np.column_stack([sc[:, 0], pts[:, 2], sc[:, 1]])
        # suspenders: from the cable down to the deck every `hangers` metres where the cable is above it
        dk, pitch = C.get("deck"), C.get("hangers", 0.0)
        if dk is not None and pitch > 0:
            along = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts[:, :2], axis=0), axis=1))]
            for sa in np.arange(pitch / 2, along[-1], pitch):
                if spec.get("side_piers") and not sides[0] < sa < sides[0] + span:
                    continue                                # the side spans stand on piers
                k = min(max(int(np.searchsorted(along, sa)) - 1, 0), len(pts) - 2)
                f = (sa - along[k]) / max(along[k + 1] - along[k], 1e-6)
                q = p3[k] + (p3[k + 1] - p3[k]) * f
                if q[1] - dk > 3:
                    m = beam(q, [q[0], dk, q[2]], 0.2, col, style_id["spire"], seed=0.3)
                    cables.append((pts[k, :2], {**{kk: m[kk] for kk in ("pos", "nrm", "uv", "idx")},
                                                "col": np.tile(col[:3], (len(m["pos"]), 1))}))
        # diagonal stays: from the saddle down to the deck, fanning out on both sides of each tower
        S = C.get("stays")
        if S and dk is not None:
            for tw in (t0, t1):
                top_p = to_scene((tw + u * off)[None], origin)[0]
                for sgn in (-1, 1):
                    for i in range(1, S["count"] + 1):
                        xy = tw + u * off + v * sgn * S["reach"] * i / S["count"]
                        q = to_scene(xy[None], origin)[0]
                        m = beam([top_p[0], top - 1.5, top_p[1]], [q[0], dk, q[1]], 0.12, col, style_id["spire"], seed=0.3)
                        cables.append((xy, {**{kk: m[kk] for kk in ("pos", "nrm", "uv", "idx")},
                                            "col": np.tile(col[:3], (len(m["pos"]), 1))}))
        # cut into pieces so each tile gets its own
        # (uv: the distance along the cable, and 50000 marking a main cable: the viewer strings its necklace
        # lights along it after dark)
        run = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p3, axis=0), axis=1))]
        step = 12
        for i in range(0, len(p3) - 1, step):
            seg = p3[i:i + step + 1]
            pos, nrm, idx = _tube(seg, C.get("radius", 0.4))
            mid = pts[min(i + step // 2, len(pts) - 1), :2]
            uv = np.column_stack([np.repeat(run[i:i + step + 1], 6), np.full(len(pos), 50000.0)])
            cables.append((mid, {"pos": pos, "nrm": nrm, "uv": uv,
                                 "col": np.tile(col[:3], (len(pos), 1)), "idx": idx.reshape(-1)}))


def _sides(side):
    return (float(side[0]), float(side[1])) if isinstance(side, (list, tuple)) else (float(side), float(side))


def _stiffening(TR, t0, t1, v, u, sides, origin, to_scene, style_id, srgb, extrude, solids, T):
    """A suspension bridge's stiffening trusses (see the docstring's `truss`): Warren trusses, a top and a
    bottom chord with diagonals and verticals per panel, in each plane, from anchorage to anchorage (or tower
    to tower), with deck slabs between the outer planes."""
    rgb = srgb(TR.get("colour", T.get("colour", "#8a8a86")))[0]
    st = style_id["spire"]
    top, depth, panel, w = TR["top"], TR["depth"], TR.get("panel", 10.0), TR.get("width", 0.6)
    towers_only = TR.get("extent", "anchorages") == "towers"
    s0 = 0.0 if towers_only else -sides[0]
    s1 = np.linalg.norm(t1 - t0) + (0.0 if towers_only else sides[1])
    n = max(1, int(round((s1 - s0) / panel)))
    ss = np.linspace(s0, s1, n + 1)
    at = lambda s, off, y: (lambda sc: [sc[0], y, sc[1]])(to_scene((t0 + v * s + u * off)[None], origin)[0])
    for off in TR["across"]:
        for i in range(n):
            a, b = ss[i], ss[i + 1]
            mid = t0 + v * (a + b) / 2 + u * off
            up = i % 2 == 0
            for p0, p1, ww in ((at(a, off, top), at(b, off, top), w * 1.4),                  # top chord
                               (at(a, off, top - depth), at(b, off, top - depth), w * 1.4),  # bottom chord
                               (at(a, off, top - depth if up else top), at(b, off, top if up else top - depth), w),
                               (at(b, off, top - depth), at(b, off, top), w * 0.8)):          # vertical
                m = beam(p0, p1, ww, rgb, st, seed=0.35)
                if m is not None:
                    solids.append((mid, m))
    # deck slabs: floors between the outer planes, in pieces of about 60 m (one tile each)
    lo, hi = min(TR["across"]), max(TR["across"])
    for fy in TR.get("floors", []):
        k = max(1, int(round((s1 - s0) / 60)))
        for a, b in zip(np.linspace(s0, s1, k + 1)[:-1], np.linspace(s0, s1, k + 1)[1:]):
            c = t0 + v * (a + b) / 2
            poly = _rect(c, u, v, lo - 0.3, hi + 0.3, -(b - a) / 2, (b - a) / 2)
            m = extrude(poly, fy, origin, rgb, (st, 0.35), base=fy - 0.8, ground=0.0, skirt=0.0)
            if m is not None:
                solids.append((c, m))


def _figure(spec, origin, terrain, style_id, srgb, to_scene, solids, lattices=None):
    c = _lonlat([spec["at"]])[0]
    g = float(terrain.height_utm([c[0]], [c[1]])[0]) + spec.get("base", 0.0)
    az = np.radians(spec.get("facing", 180.0))
    fwd = np.array([np.sin(az), np.cos(az)])           # map east, north
    right = np.array([fwd[1], -fwd[0]])
    cs = to_scene(c[None], origin)[0]
    st = style_id[spec.get("style", "plain")]
    seed = spec.get("variant", 0.5)                      # the style parameter (floodlit: the floodlight's strength)
    base_rgb = srgb(spec.get("colour", "#6fa9a3"))[0]

    def world(x, y, z):
        m = c + right * x + fwd * z
        s = to_scene(m[None], origin)[0]
        return [s[0], g + y, s[1]]

    def mesh(pos, nrm, idx, rgb, top, uv=None):
        n = len(pos)
        return {"pos": np.asarray(pos, float), "nrm": np.asarray(nrm, float), "uv": np.zeros((n, 2)) if uv is None else uv,
                "col": np.tile([*rgb[:3], 0.0], (n, 1)), "fac": np.tile([st + 0.999 * seed, top], (n, 1)),
                "base": np.tile([g, 0.0], (n, 1)), "idx": np.asarray(idx).reshape(-1)}

    def rot_n(nrm):
        """Directions from the figure's frame to the scene's."""
        n = np.asarray(nrm, float)
        e = right[0] * n[:, 0] + fwd[0] * n[:, 2]
        north = right[1] * n[:, 0] + fwd[1] * n[:, 2]
        return np.column_stack([e, n[:, 1], -north])

    top = spec.get("top") or max([s[0] for s in spec.get("sections", [])] + [p[2] for p in spec.get("prisms", [])]
                                 + [0.0] + ([spec["model"]["height"]] if "model" in spec else []))
    if "model" in spec:
        pos, nrm, idx, tip = _model(spec["model"])
        mesh_ = mesh([world(*q) for q in pos], rot_n(nrm), idx, base_rgb, top)
        if tip is not None:
            mesh_["col"][tip, :3] = srgb(spec["model"]["tip"][1])[0][:3]
            mesh_["fac"][tip, 0] = st + 0.999 * 0.99       # a style parameter of 0.98+: glows (floodlit style)
        solids.append((c, mesh_))
    if spec.get("sections"):
        k = int(spec.get("segments", 16))
        ang = np.linspace(0, 2 * np.pi, k, endpoint=False)
        rings = [[world(x + rx * np.cos(a), y, z + rz * np.sin(a)) for a in ang] for y, x, z, rx, rz in spec["sections"]]
        pos, nrm, idx = _loft(rings)
        solids.append((c, mesh(pos, nrm, idx, base_rgb, top)))
    def solid(ring, a0, a1, rgb, scale, plane, tops=None):
        """A outline (convex or not) extruded from a0 to a1, its far end scaled by `scale` about the outline's
        centroid: plane "xz" (a prism standing on the ground, a0/a1 heights) or "xy" (a slab: the outline in
        the figure's elevation, a0/a1 along z, front to back). `tops` (plane "xz", scale 1): the top's height
        at each outline point instead of a1 (a wedge: a sloped or curved roof, flat-shaded per triangle)."""
        ring = np.ascontiguousarray(ring, float)
        area2 = np.sum(ring[:, 0] * np.roll(ring[:, 1], -1) - np.roll(ring[:, 0], -1) * ring[:, 1])
        if area2 < 0:                                               # counter-clockwise in its plane
            ring = np.ascontiguousarray(ring[::-1])
            tops = None if tops is None else list(tops)[::-1]
        m = len(ring)
        cen = ring.mean(0)
        far = cen + (ring - cen) * scale

        def P(q, t):
            return [q[0], t, q[1]] if plane == "xz" else [q[0], q[1], t]

        def N(n2, t):                                               # a normal in the plane, t along the axis
            return [n2[0], t, n2[1]] if plane == "xz" else [n2[0], n2[1], t]
        pos, nrm, idx, groups = [], [], [], []
        for i in range(m):                                          # walls, outward normals
            a, b, A, B = ring[i], ring[(i + 1) % m], far[i], far[(i + 1) % m]
            q0, q1, q2, q3 = P(a, a0), P(b, a0), P(B, a1), P(A, a1)
            if tops is not None:
                q2, q3 = P(B, tops[(i + 1) % m]), P(A, tops[i])
            n = np.cross(np.subtract(q1, q0), np.subtract(q3, q0))
            if np.linalg.norm(n) < 1e-9:
                n = np.cross(np.subtract(q2, q1), np.subtract(q1, q0))
            n = n / max(np.linalg.norm(n), 1e-9)
            o = np.array(N([b[1] - a[1], -(b[0] - a[0])], 0.0))   # outward in the plane
            if plane == "xy":
                o = np.array([b[1] - a[1], -(b[0] - a[0]), 0.0])
            if n @ o < 0:
                n = -n
            b0 = len(pos)
            pos += [q0, q1, q2, q3]
            nrm += [n] * 4
            idx += [[b0, b0 + 1, b0 + 2], [b0, b0 + 2, b0 + 3]]
            groups.append((b0, b0 + 4))
        tri = np.asarray(earcut.triangulate_float64(ring, np.array([m], np.uint32))).reshape(-1, 3)
        for r_, t, up in ((ring, a0, -1.0), (far, a1, 1.0)):       # caps
            if scale < 1e-3 and up > 0:
                continue
            if tops is not None and up > 0:                         # a wedge's top: a face normal per triangle
                for tr in tri:
                    q = [[r_[k][0], tops[k], r_[k][1]] for k in tr]
                    n = np.cross(np.subtract(q[1], q[0]), np.subtract(q[2], q[0]))
                    n = n / max(np.linalg.norm(n), 1e-9) * (1.0 if n[1] >= 0 else -1.0)
                    b0 = len(pos)
                    pos += q
                    nrm += [list(n)] * 3
                    idx += [[b0, b0 + 1, b0 + 2]]
                    groups.append((b0, b0 + 3))
                continue
            b0 = len(pos)
            pos += [P(q, t) for q in r_]
            nrm += [N([0.0, 0.0], up)] * m
            idx += [[b0 + int(k) for k in tr] for tr in tri]
            groups.append((b0, b0 + m))
        # the facade shader's wall run (metres along the face, the face's width) on every face that is a wall
        # (a slab's elevation, a prism's sides); roofs and floors keep 0/0
        P_, N_ = np.asarray(pos, float), np.asarray(nrm, float)
        uv = np.zeros((len(P_), 2))
        for g0, g1 in (groups if spec.get("walls") else []):
            n_ = N_[g0]
            if abs(n_[1]) > 0.7:
                continue
            t_ = np.array([n_[2], 0.0, -n_[0]])
            t_ /= max(np.linalg.norm(t_), 1e-9)
            sv = P_[g0:g1] @ t_
            sv -= sv.min()
            uv[g0:g1, 0], uv[g0:g1, 1] = sv, sv.max()
        W, Nw = np.array([world(*q) for q in pos]), rot_n(nrm)
        idx = np.array(idx)
        # each triangle wound to face its normal in the scene (the frame's handedness differs from the scene's)
        g = np.cross(W[idx[:, 1]] - W[idx[:, 0]], W[idx[:, 2]] - W[idx[:, 0]])
        flip = np.einsum("ij,ij->i", g, Nw[idx[:, 0]]) < 0
        idx[flip] = idx[flip][:, [0, 2, 1]]
        solids.append((c, mesh(W, Nw, idx, rgb, top, uv)))

    for pr in spec.get("prisms", []):
        # [outline [[x, z], ...], y0, y1, colour?, top scale?]: a prism, tapering to `top scale` (0: a pyramid)
        solid(pr[0], pr[1], pr[2], srgb(pr[3])[0] if len(pr) > 3 and pr[3] else base_rgb,
              float(pr[4]) if len(pr) > 4 else 1.0, "xz")
    for wd in spec.get("wedges", []):
        # [outline [[x, z, top], ...], y0, colour?]: a prism from y0 to its own top at each outline point
        solid([q[:2] for q in wd[0]], wd[1], max(q[2] for q in wd[0]),
              srgb(wd[2])[0] if len(wd) > 2 and wd[2] else base_rgb, 1.0, "xz", tops=[q[2] for q in wd[0]])
    for sl in spec.get("slabs", []):
        # [outline [[x, y], ...] in the elevation, z0, z1, colour?, back scale?]: arches, pediments, gables
        solid(sl[0], sl[1], sl[2], srgb(sl[3])[0] if len(sl) > 3 and sl[3] else base_rgb,
              float(sl[4]) if len(sl) > 4 else 1.0, "xy")
    for t in spec.get("tubes", []):
        p0, p1, r = t[0], t[1], t[2]
        rgb = srgb(t[3])[0] if len(t) > 3 else base_rgb
        loc = np.linspace(p0, p1, 6)
        pts = np.array([world(*q) for q in loc])
        pos, nrm, idx = _tube(pts, r, 8)
        solids.append((c, mesh(pos, nrm, idx, rgb, top)))
    # glazing: see-through sheets (glass domes and vaults, a fabric tent) into the tile's lattice mesh
    sheets = []
    for gz in spec.get("glazing", []) if lattices is not None else []:
        grid = np.asarray(gz["grid"], float)                       # m rows of n points (x, y, z) in the frame
        m_, n_ = grid.shape[:2]
        pu, pv = gz.get("period", [3.0, 3.0])
        seg_r = np.linalg.norm(np.diff(grid, axis=1), axis=2)       # along the rows
        seg_c = np.linalg.norm(np.diff(grid, axis=0), axis=2)       # along the columns
        s_r = np.concatenate([np.zeros((m_, 1)), np.cumsum(seg_r, 1)], 1)
        long = int(np.argmax(s_r[:, -1]))
        u_ = np.tile(s_r[long] / pu, (m_, 1))                       # members along the columns: the longest row's spacing
        v_ = np.concatenate([np.zeros((1, n_)), np.cumsum(seg_c, 0)], 0) / pv
        P = np.array([world(*q) for q in grid.reshape(-1, 3)])
        i, j = np.meshgrid(np.arange(m_ - 1), np.arange(n_ - 1), indexing="ij")
        a = (i * n_ + j).ravel()
        idx = np.concatenate([np.stack([a, a + 1, a + n_ + 1], 1), np.stack([a, a + n_ + 1, a + n_], 1)])
        fn = np.cross(P[idx[:, 1]] - P[idx[:, 0]], P[idx[:, 2]] - P[idx[:, 0]])
        nrm = np.zeros_like(P)
        for k in range(3):
            np.add.at(nrm, idx[:, k], fn)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True).clip(1e-9)
        kind = 4 if gz.get("kind") == "fabric" else 3
        rgb = srgb(gz["colour"])[0] if gz.get("colour") else base_rgb
        sheets.append({"pos": P, "nrm": nrm, "uv": np.column_stack([u_.ravel(), v_.ravel()]),
                       "col": np.tile([*rgb[:3], kind / 255], (len(P), 1)), "idx": idx.reshape(-1)})
    if sheets:
        out, off = {k: [] for k in sheets[0]}, 0
        for sh in sheets:
            for k, v in sh.items():
                out[k].append(v + off if k == "idx" else v)
            off += len(sh["pos"])
        lattices.append((c, {k: np.concatenate(v) for k, v in out.items()}))
    for bx in spec.get("boxes", []):
        x, y, z, sx, sy, sz = bx[:6]
        rgb = srgb(bx[6])[0] if len(bx) > 6 else base_rgb
        corners = np.array([[x + i * sx / 2, y + j * sy / 2, z + l * sz / 2] for i in (-1, 1) for j in (-1, 1) for l in (-1, 1)])
        faces = [(0, 1, 3, 2, [-1, 0, 0]), (4, 6, 7, 5, [1, 0, 0]), (0, 4, 5, 1, [0, -1, 0]), (2, 3, 7, 6, [0, 1, 0]),
                 (0, 2, 6, 4, [0, 0, -1]), (1, 5, 7, 3, [0, 0, 1])]
        pos, nrm, idx = [], [], []
        for f in faces:
            b0 = len(pos)
            for q in f[:4]:
                pos.append(world(*corners[q]))
            nrm += [f[4]] * 4
            idx += [[b0, b0 + 1, b0 + 2], [b0, b0 + 2, b0 + 3]]
        solids.append((c, mesh(pos, rot_n(nrm), idx, rgb, top)))


def _model(M):
    """A figure's mesh from a file (see the docstring's `model`) in the figure frame (x right, y up from the cut,
    z forward), metres: pos, nrm, idx and the vertices of its tip (or None)."""
    import meshoptimizer
    import trimesh
    from ..common import DATA
    m = trimesh.load(DATA / M["file"], force="scene")
    m = m.to_geometry() if hasattr(m, "to_geometry") else m.dump(concatenate=True)
    m.merge_vertices()                                     # scans come in chunks of 65k vertices
    axis = lambda a: np.eye(3)["xyz".index(a[-1])] * (-1.0 if a[0] == "-" else 1.0)
    up, fwd = axis(M.get("up", "+y")), axis(M.get("front", "+z"))
    right = np.cross(fwd, up)
    if (np.asarray(m.vertices) @ up).min() < M["cut"] - 1e-6:   # (nothing under the cut: no slice; its cap needs networkx)
        m = m.slice_plane(up * M["cut"], up, cap=True)
    v = np.ascontiguousarray(m.vertices, np.float32)
    f = np.ascontiguousarray(m.faces.reshape(-1), np.uint32)
    dst = np.zeros_like(f)
    n = meshoptimizer.simplify(dst, f, v, target_index_count=int(M.get("triangles", 60000)) * 3, target_error=0.05)
    used, inv = np.unique(dst[:n], return_inverse=True)
    s = trimesh.Trimesh(v[used], inv.reshape(-1, 3), process=False)
    p = np.asarray(s.vertices, float)
    h = p @ up - M["cut"]
    scale = M["height"] / h.max()
    feet = p[h < 0.1 * h.max()]                            # stood on the centre of its lowest tenth
    o = feet.mean(0)
    q = np.column_stack([(p - o) @ right, h, (p - o) @ fwd]) * scale
    nn = np.asarray(s.vertex_normals, float)
    nrm = np.column_stack([nn @ right, nn @ up, nn @ fwd])
    tip = np.flatnonzero(q[:, 1] > M["height"] - M["tip"][0]) if "tip" in M else None
    print(f"structures: model {M['file']}: {len(s.faces):,} triangles, {scale:.3f} m per unit")
    return q, nrm, np.asarray(s.faces).reshape(-1), tip


def _truss(spec, origin, terrain, extrude, style_id, srgb, solids):
    a, v, along = span_axis(spec["name"])
    if spec.get("piers"):                                  # pier sites given: the axis runs through them
        P = _lonlat(spec["piers"])
        cP = P.mean(0)
        if len(P) >= 2:
            _, _, vt = np.linalg.svd(P - cP, full_matrices=False)
            v2 = vt[0] * np.sign(vt[0] @ v)
            a, v = cP + v2 * ((a - cP) @ v2), v2
        along = np.sort((P - a) @ v)
    if len(along) < 2:
        print(f"structures: {spec['name']}: its deck crosses no water; left out")
        return
    u = np.array([v[1], -v[0]])
    W, deck, low, peak = spec["width"], spec["deck"], spec["low"], spec["peak"]
    st = style_id[spec.get("style", "lattice")]
    rgb = srgb(spec.get("colour", "#8a8f8c"))[0]
    prgb = srgb(spec.get("pier_colour", "#a89f90"))[0]
    arch = spec.get("shape", "cantilever") == "arch"
    if spec.get("anchors"):                                # the anchor arms' ends
        x0, x1 = sorted((_lonlat(spec["anchors"]) - a) @ v)
    else:
        x0, x1 = along[0] - spec.get("reach", 40.0), along[-1] + spec.get("reach", 40.0)
    pw, pl = spec.get("pier_size", [W + 4, 12.0])
    TW = spec.get("tower")                                 # an arch's stone towers: {height, across, along}
    for x in along:                                        # piers from the water to the deck
        c = a + v * x
        if arch and TW:
            solids.append((c, extrude(_rect(c, u, v, -TW["across"] / 2, TW["across"] / 2, -TW["along"] / 2, TW["along"] / 2),
                                      TW["height"], origin, prgb, (style_id["plain"], 0.3), ground=0.0, skirt=2.0)))
            continue
        solids.append((c, extrude(_rect(c, u, v, -pw / 2, pw / 2, -pl / 2, pl / 2), deck - 3, origin, prgb,
                                  (style_id["plain"], 0.3), ground=0.0, skirt=2.0)))
        if arch:                                           # the arch's stone towers at its ends
            solids.append((c, extrude(_rect(c, u, v, -W / 2 - 3, W / 2 + 3, -8, 8), peak * 0.8, origin, prgb,
                                      (style_id["plain"], 0.3), base=deck - 3, ground=0.0)))
    # members: bottom chord at the deck (an arch: its rib), top chord along the profile, verticals and
    # alternating diagonals on both sides, cross beams over the top (open: the sky shows through)
    step = spec.get("panel", 10.0)
    xs = np.arange(x0, x1 + 0.1, step)
    if arch:                                               # between the towers only
        xs = np.arange(along[0], along[-1] + 0.1, (along[-1] - along[0]) / max(1, round((along[-1] - along[0]) / step)))
    rib = spec.get("rib")                                  # [spring, crown]: a two-hinged arch's lower chord

    def top_at(x):
        if arch:
            f = np.clip((x - along[0]) / (along[-1] - along[0]), 0, 1)
            return low + (peak - low) * np.sin(np.pi * f)
        d = np.min(np.abs(along - x))
        return low + (peak - low) * max(0.0, 1 - d / spec.get("fall", 60.0)) ** 1.3

    def bottom_at(x):
        if arch and rib:
            f = np.clip((x - along[0]) / (along[-1] - along[0]), 0, 1)
            return rib[0] + (rib[1] - rib[0]) * (1 - (2 * f - 1) ** 2)
        return deck - 2.5
    from .tiles import to_scene
    for side in (-1, 1):
        pts = [a + v * x + u * side * W / 2 for x in xs]
        sc = to_scene(np.array(pts), origin)
        tops = [top_at(x) for x in xs]
        bots = [bottom_at(x) for x in xs]
        for i in range(len(xs)):
            P = lambda k, y: [sc[k][0], y, sc[k][1]]
            members = [beam(P(i, bots[i]), P(i, tops[i]), 0.9, rgb, st)]
            if arch and rib and bots[i] > deck + 1:        # the deck hangs from the rib
                members.append(beam(P(i, deck - 1), P(i, bots[i]), 0.5, rgb, st))
            if i + 1 < len(xs):
                members += [beam(P(i, bots[i]), P(i + 1, bots[i + 1]), 1.6 if rib else 1.2, rgb, st),
                            beam(P(i, tops[i]), P(i + 1, tops[i + 1]), 1.2, rgb, st),
                            beam(P(i, bots[i] if i % 2 else tops[i]), P(i + 1, tops[i + 1] if i % 2 else bots[i + 1]), 0.7, rgb, st)]
            for m in members:
                if m is not None:
                    solids.append((pts[i], m))
    for x in xs[::2]:
        pa, pb = a + v * x - u * W / 2, a + v * x + u * W / 2
        sa, sb = to_scene(np.array([pa, pb]), origin)
        y = top_at(x)
        m = beam([sa[0], y, sa[1]], [sb[0], y, sb[1]], 0.8, rgb, st)
        if m is not None:
            solids.append((pa, m))
    PT = spec.get("pier_towers")                           # {height, spire, width}: posts and spires over the piers
    if PT:
        for x in along:
            c = a + v * x
            hw, hd = W / 2, PT.get("depth", 8.0) / 2
            corners = [c + u * su * hw + v * sv * hd for su in (-1, 1) for sv in (-1, 1)]
            sc = to_scene(np.array(corners), origin)
            for k, q in enumerate(sc):
                for m in (beam([q[0], deck, q[1]], [q[0], PT["height"], q[1]], PT.get("width", 1.6), rgb, st),
                          beam([q[0], PT["height"], q[1]], [q[0], PT["height"] + PT.get("spire", 10.0), q[1]], 0.5, rgb, st)):
                    if m is not None:
                        solids.append((c, m))
            for i, j in ((0, 2), (1, 3), (0, 1), (2, 3)):  # a frame round the top
                m = beam([sc[i][0], PT["height"] - 1, sc[i][1]], [sc[j][0], PT["height"] - 1, sc[j][1]], 1.2, rgb, st)
                if m is not None:
                    solids.append((c, m))


def _rot(k, p):
    """Frame points (n, 3) turned k quarter turns about the vertical: a tower's four sides or legs."""
    p = np.atleast_2d(np.asarray(p, float))
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    x, z = ((x, z), (z, -x), (-x, -z), (-z, x))[k % 4]
    return np.column_stack([x, y, z])


def _lattice_tower(spec, origin, terrain, style_id, srgb, to_scene, solids, lattices):
    """A lattice tower on four legs (see the docstring's `lattice_tower`): bars into solids, the braced panels
    into lattices (one mesh, at the tower's centre, so it lands in one tile: one draw call)."""
    from scipy.interpolate import PchipInterpolator
    c = _lonlat([spec["at"]])[0]
    g = float(terrain.height_utm([c[0]], [c[1]])[0]) + spec.get("base", 0.0)
    az = np.radians(spec.get("facing", 0.0))
    fwd = np.array([np.sin(az), np.cos(az)])           # map east, north
    right = np.array([fwd[1], -fwd[0]])
    cs = to_scene(c[None], origin)[0]
    R = to_scene((c + right)[None], origin)[0] - cs      # the frame's x and z in the scene (x, z)
    F = to_scene((c + fwd)[None], origin)[0] - cs

    def W(p):
        p = np.atleast_2d(np.asarray(p, float))
        return np.column_stack([cs[0] + p[:, 0] * R[0] + p[:, 2] * F[0], g + p[:, 1],
                                cs[1] + p[:, 0] * R[1] + p[:, 2] * F[1]])

    stops = spec.get("colours") or [[0.0, spec.get("colour", "#7a6a58")]]
    sy = np.array([s[0] for s in stops], float)
    sc = np.array([srgb(s[1])[0] for s in stops], float)
    colour = lambda y: np.array([np.interp(y, sy, sc[:, k]) for k in range(3)])
    st = style_id[spec.get("style", "floodlit")]
    seed = spec.get("variant", 0.5)
    top = float(spec["height"])
    seg = spec.get("segment", 6.0)
    n_bars = [0]

    def bar(p0, p1, w, d=None):
        m = beam(W(p0)[0], W(p1)[0], w, colour(0.5 * (p0[1] + p1[1])), st, seed, d)
        if m is not None:
            m["fac"][:, 1] = top
            m["base"][:, 0] = g
            solids.append((c, m))
            n_bars[0] += 1

    sheets = []

    def sheet(rows, uvs, kind):
        """A lattice sheet through a grid of frame points (m rows of n), with pattern coordinates per point."""
        rows = np.asarray(rows, float)
        m_, n_ = rows.shape[:2]
        P = W(rows.reshape(-1, 3))
        i, j = np.meshgrid(np.arange(m_ - 1), np.arange(n_ - 1), indexing="ij")
        a = (i * n_ + j).ravel()
        idx = np.concatenate([np.stack([a, a + 1, a + n_ + 1], 1), np.stack([a, a + n_ + 1, a + n_], 1)])
        fn = np.cross(P[idx[:, 1]] - P[idx[:, 0]], P[idx[:, 2]] - P[idx[:, 0]])
        nrm = np.zeros_like(P)
        for k in range(3):
            np.add.at(nrm, idx[:, k], fn)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True).clip(1e-9)
        col = np.array([[*colour(y), kind / 255] for y in rows.reshape(-1, 3)[:, 1]])
        sheets.append({"pos": P, "nrm": nrm, "uv": np.asarray(uvs, float).reshape(-1, 2), "col": col,
                       "idx": idx.reshape(-1)})

    def along(pts, width):
        """Pattern v up a strip: its slant length in widths (panels come out as square as the strip is wide)."""
        d = np.r_[0, np.linalg.norm(np.diff(pts, axis=0), axis=1)]
        w = np.maximum(width, 0.1)
        return np.cumsum(d / np.r_[w[0], 0.5 * (w[1:] + w[:-1])])

    # the legs: sections of a box at each corner of the square, `inner` to `outer` in x and z
    sections = []
    for L in spec.get("legs", []):
        pr = np.asarray(L["profile"], float)
        o, i_ = PchipInterpolator(pr[:, 0], pr[:, 1]), PchipInterpolator(pr[:, 0], pr[:, 2])
        sections.append((pr[0, 0], pr[-1, 0], o, i_))
        ys = np.linspace(pr[0, 0], pr[-1, 0], max(3, int(np.ceil((pr[-1, 0] - pr[0, 0]) / seg))) + 1)
        O, I = o(ys), i_(ys)
        cw = np.clip(L.get("chord", 0.08) * (O - I), 0.4, 3.0)
        panel = L.get("panel", 1.0)
        corners = {"A": np.column_stack([O, ys, O]), "B": np.column_stack([O, ys, I]),
                   "C": np.column_stack([I, ys, I]), "D": np.column_stack([I, ys, O])}
        for k in range(4):
            cr = {n: _rot(k, p) for n, p in corners.items()}
            for n in "ABCD":
                for q in range(len(ys) - 1):
                    bar(cr[n][q], cr[n][q + 1], 0.5 * (cw[q] + cw[q + 1]))
            for e0, e1 in (("A", "D"), ("A", "B"), ("B", "C"), ("D", "C")):
                mid = 0.5 * (cr[e0] + cr[e1])
                v = along(mid, O - I) / panel
                sheet(np.stack([cr[e0], cr[e1]], 1), np.stack([np.column_stack([np.zeros_like(v), v]),
                                                               np.column_stack([np.ones_like(v), v])], 1), 0)

    def prof(y):
        s = [t for t in sections if t[0] - 1e-6 <= y] or sections[:1]
        return float(s[-1][2](y)), float(s[-1][3](y))

    # braced faces between the legs (the shaft), on the outer plane from one leg's inner edge to the next's
    for y0, y1 in spec.get("faces", []):
        ys = np.linspace(y0, y1, max(3, int(np.ceil((y1 - y0) / seg))) + 1)
        OI = np.array([prof(y) for y in ys])
        O, I = OI[:, 0], OI[:, 1]
        for k in range(4):
            l, r = _rot(k, np.column_stack([-I, ys, O])), _rot(k, np.column_stack([I, ys, O]))
            v = along(0.5 * (l + r), 2 * O)
            u0, u1 = 0.5 - I / (2 * O), 0.5 + I / (2 * O)
            sheet(np.stack([l, r], 1), np.stack([np.column_stack([u0, v]), np.column_stack([u1, v])], 1), 0)

    # the arches under the first deck: a round rib on each face, lattice spandrels over it up to the deck's belt
    A = spec.get("arches")
    if A:
        ys_, crown, rib, inset = A["spring"], A["crown"], A.get("rib", 3.0), A.get("inset", 1.5)
        xs = prof(ys_)[1]
        h = crown - ys_
        Rr = (xs * xs + h * h) / (2 * h)
        cy = crown - Rr
        th0 = np.arcsin(np.clip((ys_ - cy) / Rr, -1, 1))
        th = np.linspace(th0, np.pi - th0, 25)
        rc = Rr + rib / 2
        depth = lambda y: np.array([prof(q)[0] for q in np.atleast_1d(y)]) - inset
        for k in range(4):
            yy = cy + rc * np.sin(th)
            pts = _rot(k, np.column_stack([rc * np.cos(th), yy, depth(yy)]))
            for q in range(len(th) - 1):
                bar(pts[q], pts[q + 1], A.get("depth", 1.6), rib)
        Re, ytop, per = Rr + rib, A["top"], A.get("period", 2.5)
        X = np.sqrt(max(Re * Re - (ytop - cy) ** 2, 0.0)) if ytop - cy < Re else Re
        xx = np.linspace(-X, X, 33)
        yb = np.maximum(cy + np.sqrt(np.clip(Re * Re - xx * xx, 0, None)), ys_)
        yb = np.minimum(yb, ytop)
        for k in range(4):
            bot = _rot(k, np.column_stack([xx, yb, depth(yb)]))
            tp = _rot(k, np.column_stack([xx, np.full_like(xx, ytop), depth(np.full_like(xx, ytop))]))
            sheet(np.stack([bot, tp]), np.stack([np.column_stack([xx / per, yb / per]),
                                                 np.column_stack([xx / per, np.full_like(xx, ytop / per)])]), 1)

    # decks: solid belts and slabs (boxes), open railings (lattice)
    boxes = list(spec.get("boxes", []))
    for b in spec.get("belts", []):
        y0, y1, hf, dp = b[:4]
        cl = b[4:5]
        ym, hh = 0.5 * (y0 + y1), y1 - y0
        for s in (-1, 1):
            boxes.append([0.0, ym, s * (hf - dp / 2), 2 * hf, hh, dp, *cl])
            boxes.append([s * (hf - dp / 2), ym, 0.0, dp, hh, 2 * hf - 2 * dp, *cl])
    for f in spec.get("floors", []):
        y, hf, vd, th_ = f[:4]
        cl = f[4:5]
        for s in (-1, 1):
            boxes.append([0.0, y - th_ / 2, s * (hf + vd) / 2, 2 * hf, th_, hf - vd, *cl])
            boxes.append([s * (hf + vd) / 2, y - th_ / 2, 0.0, hf - vd, th_, 2 * vd, *cl])
    for y0, y1, hf in spec.get("railings", []):
        for k in range(4):
            l, r = _rot(k, [[-hf, y0, hf], [-hf, y1, hf]]), _rot(k, [[hf, y0, hf], [hf, y1, hf]])
            sheet(np.stack([l, r], 1), [[[-hf / 1.3, 0], [hf / 1.3, 0]], [[-hf / 1.3, 1], [hf / 1.3, 1]]], 2)
    # braced frustums (the campanile): four panels and four corner posts
    for y0, y1, h0, h1 in spec.get("frustums", []):
        ys = np.linspace(y0, y1, max(2, int(np.ceil((y1 - y0) / seg))) + 1)
        H = h0 + (h1 - h0) * (ys - y0) / (y1 - y0)
        for k in range(4):
            l, r = _rot(k, np.column_stack([-H, ys, H])), _rot(k, np.column_stack([H, ys, H]))
            v = along(0.5 * (l + r), 2 * H)
            sheet(np.stack([l, r], 1), np.stack([np.column_stack([np.zeros_like(v), v]),
                                                 np.column_stack([np.ones_like(v), v])], 1), 0)
            bar(r[0], r[-1], spec.get("post", 0.7))
    if sheets:
        out, off = {k: [] for k in sheets[0]}, 0
        for s in sheets:
            for k, v in s.items():
                out[k].append(v + off if k == "idx" else v)
            off += len(s["pos"])
        lat = {k: np.concatenate(v) for k, v in out.items()}
        lattices.append((c, lat))
    fig = {k: spec[k] for k in ("at", "base", "facing", "variant", "tubes", "prisms") if k in spec}
    fig.update(style=spec.get("style", "floodlit"), colour=spec.get("colour", stops[len(stops) // 2][1]),
               boxes=boxes, top=top)
    before = len(solids)
    _figure(fig, origin, terrain, style_id, srgb, to_scene, solids)
    tri_s = sum(len(m["idx"]) // 3 for _, m in solids[before:])
    print(f"structures: {spec.get('name', 'lattice tower')}: {n_bars[0]} bars ({12 * n_bars[0]:,} triangles), "
          f"{len(solids) - before} boxes/tubes ({tri_s:,}), lattice {len(lat['idx']) // 3 if sheets else 0:,} triangles")
