"""M4 (builder T): the [[structures]] figures for the modern landmarks the building table can't make, written to
generated/structures-m4t.toml (city.toml `include`s it; run again after editing this file).

- the Sony Center's tent roof (a light membrane cone on its ring over the forum; the LoD2's ~50 canopy solids
  8-24 m thick are excluded in [buildings]);
- the Haus der Kulturen der Welt's shell roof (the 'pregnant oyster': a saddle shell on two abutments; the LoD2's
  1,482 m² canopy box 14-24 m is excluded);
- the Park Inn's antenna to 149.5 m, the Europa-Center's Mercedes star to 103 m, the Kollhoff-Tower's lantern and
  mast to 115 m.
Positions from the building table (the canopy pieces' peak, the towers' top pieces), dimensions from the notes in
data/landmarks_berlin.csv and refs/ photos (est.).

    uv run python scripts/m4t_structures.py
"""
import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "generated" / "structures-m4t.toml"


def f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def arr(rows):
    return "[" + ",\n    ".join(rows) + "]"


def sony():
    # the oval ring 92 x 74 m (long axis at 163 deg; 104 x 82 cut into the ring buildings), from the surrounding roofs at ~39 m to the peak ring at ~65 m;
    # concave sides ('Mount Fuji'); a short mast through the oculus.
    # (M4 fix round, builder L: the critic read an opaque white cone) the membrane as a translucent `glazing` sheet of
    # kind fabric (the lattice mesh: the sky and the forum show through it), its radial cables every ~11 m round the
    # outer ring and the rings as the members; the outer compression ring, the oculus ring and the mast solid
    rings = [(0, 1.0), (3, 0.86), (6, 0.72), (9, 0.58), (12, 0.45), (15, 0.34), (18, 0.25), (21, 0.17), (24, 0.11), (26, 0.075)]
    n = 48
    grid = []
    for y, k in rings:
        grid.append("[" + ", ".join(f"[{f(37 * k * math.cos(2 * math.pi * j / n))}, {y}, {f(46 * k * math.sin(2 * math.pi * j / n))}]"
                                    for j in range(n + 1)) + "]")
    tubes = ['[[0, 20, 0], [0, 31, 0], 0.45, "#9a9ea2"]']
    for y, k, r in ((0.2, 1.0, 0.7), (26.0, 0.075, 0.35)):
        pts = [(37 * k * math.cos(2 * math.pi * j / 32), y, 46 * k * math.sin(2 * math.pi * j / 32)) for j in range(33)]
        tubes += [f"[[{f(a[0])}, {a[1]}, {f(a[2])}], [{f(b[0])}, {b[1]}, {f(b[2])}], {r}, \"#8f9497\"]" for a, b in zip(pts, pts[1:])]
    return f'''[[structures]]
kind = "figure"
name = "Sony Center roof"
at = [13.373333, 52.510006]
base = 39.0
facing = 163
style = "floodlit"
variant = 0.5
colour = "#dcd9d0"
top = 28.5
tubes = {arr(tubes)}
[[structures.glazing]]
kind = "fabric"
colour = "#ecebe6"
period = [10.8, 4.0]
grid = {arr(grid)}
'''


def hkw():
    # a saddle shell: arches spanning 64 m across (E-W) on two abutments at the podium, higher at the front and
    # back edges than in the middle; 0.9 m thick, seven bands front to back
    span, t = 32.0, 0.9
    rises = [16.0, 13.2, 11.4, 10.8, 11.4, 13.2, 16.0]
    zs = [-31.5, -22.5, -13.5, -4.5, 4.5, 13.5, 22.5, 31.5]
    slabs = []
    for i, H in enumerate(rises):
        n = 14
        outer = [(span * math.cos(math.pi * j / n), H * math.sin(math.pi * j / n)) for j in range(n + 1)]
        inner = [((span - 2.5) * math.cos(math.pi * j / n), (H - t) * math.sin(math.pi * j / n)) for j in range(n, -1, -1)]
        pts = ", ".join(f"[{f(x)}, {f(max(y, 0.0))}]" for x, y in outer + inner)
        slabs.append(f"[[{pts}], {f(zs[i])}, {f(zs[i + 1])}]")
    return f'''[[structures]]
kind = "figure"
name = "Haus der Kulturen der Welt roof"
at = [13.364822, 52.518744]
base = 6.5
facing = 0
style = "floodlit"
variant = 0.4
colour = "#e6e4de"
top = 16.0
slabs = {arr(slabs)}
'''


def park_inn():
    # the antenna mast on the roof (the slab 125 m, its sign bands to 132; 149.5 m to the tip, DE): a lattice mast
    # as a tube with two shorter whips
    return '''[[structures]]
kind = "figure"
name = "Park Inn antenna"
at = [13.41276, 52.522941]
base = 125.0
facing = 127
style = "plain"
variant = 0.3
colour = "#c8c8c4"
top = 24.5
prisms = [[[[-4.5, -3.0], [4.5, -3.0], [4.5, 3.0], [-4.5, 3.0]], 0, 7.0, "#b9bbbd"]]
tubes = [[[0, 7, 0], [0, 24.5, 0], 0.55], [[3.2, 7, 1.5], [3.2, 13.5, 1.5], 0.25], [[-3.2, 7, -1.5], [-3.2, 12, -1.5], 0.25]]
'''


def europa():
    # the rotating Mercedes star over the roof (86-90 m): a ring ~10 m across on a mast, the three-pointed star inside
    # it; 103 m to its top (DE)
    r, cy = 5.0, 7.6
    tubes = [f"[[0, 0, 0], [0, {f(cy - r)}, 0], 0.5]"]
    n = 20
    for j in range(n):
        a0, a1 = 2 * math.pi * j / n, 2 * math.pi * (j + 1) / n
        tubes.append(f"[[{f(r * math.sin(a0))}, {f(cy + r * math.cos(a0))}, 0], "
                     f"[{f(r * math.sin(a1))}, {f(cy + r * math.cos(a1))}, 0], 0.32]")
    for a in (0, 120, 240):
        a = math.radians(a)
        tubes.append(f"[[0, {f(cy)}, 0], [{f(r * math.sin(a))}, {f(cy + r * math.cos(a))}, 0], 0.38]")
    return f'''[[structures]]
kind = "figure"
name = "Europa-Center star"
at = [13.338042, 52.504334]
base = 89.8
facing = 190
style = "floodlit"
variant = 0.6
colour = "#d8dadc"
top = 13.0
tubes = {arr(tubes)}
'''


def kollhoff():
    # the copper-green pyramid lantern on the stepped crown and its mast: 103 m roof, 115 m to the tip
    return '''[[structures]]
kind = "figure"
name = "Kollhoff-Tower lantern"
at = [13.375027, 52.508989]
base = 102.8
facing = 144.5
style = "floodlit"
variant = 0.3
colour = "#6f9486"
top = 12.2
prisms = [[[[-4.2, -2.0], [4.2, -2.0], [4.2, 2.0], [-4.2, 2.0]], 0, 4.2, "#6f9486", 0.15]]
tubes = [[[0, 4.0, 0], [0, 12.2, 0], 0.22, "#8a8f92"]]
'''


def lehrer():
    # Womacka's frieze 'Unser Leben' (1964): a ~7 m coloured band round the slab over the glazed ground floor (refs
    # alexanderplatz-towers/03); the slab's footprint 44.7 x 15.4 m at bearing 38.7 (the building table), the band
    # 0.25 m proud of it in coloured panels (strong red, ochre, blue and green on grey, est.)
    L, W, y0, y1, d = 44.7 / 2 + 0.25, 15.4 / 2 + 0.25, 6.6, 13.4, 0.35
    cols = ["#4f6f98", "#b0553d", "#c9a042", "#5d8a6a", "#8a8f96", "#3f5f8a", "#c46a3a"]
    prisms, k = [], 0
    for side in (-1, 1):                       # the long faces: 7 panels each
        for i in range(7):
            z0, z1 = -L + 2 * L * i / 7, -L + 2 * L * (i + 1) / 7
            x0, x1 = (W - d, W) if side > 0 else (-W, -W + d)
            prisms.append(f"[[[{f(x0)}, {f(z0)}], [{f(x1)}, {f(z0)}], [{f(x1)}, {f(z1)}], [{f(x0)}, {f(z1)}]], {y0}, {y1}, \"{cols[k % 7]}\"]")
            k += 1
    for side in (-1, 1):                       # the short ends: one panel each
        z0, z1 = (L - d, L) if side > 0 else (-L, -L + d)
        prisms.append(f"[[[{f(-W)}, {f(z0)}], [{f(W)}, {f(z0)}], [{f(W)}, {f(z1)}], [{f(-W)}, {f(z1)}]], {y0}, {y1}, \"{cols[(k + 3) % 7]}\"]")
        k += 1
    return f'''[[structures]]
kind = "figure"
name = "Haus des Lehrers frieze"
at = [13.416343, 52.521235]
base = 0.0
facing = 38.7
style = "floodlit"
variant = 0.2
colour = "#8a8f96"
top = 58.8
prisms = {arr(prisms)}
'''


def main():
    block = "\n".join(["# Generated by scripts/m4t_structures.py: do not edit (edit the script and run it again).",
                       "# city.toml's `include` list lays this file under its own settings.", "",
                       sony(), hkw(), park_inn(), europa(), kollhoff(), lehrer()]) + "\n"
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(block)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
