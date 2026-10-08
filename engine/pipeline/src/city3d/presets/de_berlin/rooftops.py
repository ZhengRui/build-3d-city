"""The de-berlin preset's rooftop clutter (06c_rooftops): europe-west's items (stacks, hatches, lanterns, plant,
solar rows, green terraces) in Berlin's programmes (region_research.md §4.2-4.4). Stacks are red brick or
plastered cream under a concrete or zinc cover slab ([rooftops] stack_cols / pot_cols, stack_cap in de-berlin.toml),
low (0.5-1.3 m over the roof), never Paris's and London's rows of terracotta pots:
  altbau     the Berliner Dach: 2-4 stacks per house in rows along the party walls (the Brandwände) and on the
             flat top's edge (coal-stove flues: 90 % of the roofs), roof windows (Dachausbau), a hatch, a green
             terrace now and then; a flat Altbau roof: stacks on its edge
  althof     courtyard wings: a stack or two, a hatch
  kma        tall stacks on the blocks (two in five), a hatch, plant
  nachkrieg  europe-west's post-war flat roof (lift housing, stair box, vents, flues), more green
  platte     lift and stair bulkheads, vents and antenna-like flues; a solar or green layer on some re-clad slabs
  hansa      flat with a roof terrace (green) on some
  neubau     modern flat roof: a set-back plant, solar rows (the Solargesetz) and green roofs (33 % of 1990s+ housing)
  beton, sandstein, klinker, kirche  europe-west's civic
  glass      europe-west's (plant, cooling towers, a gantry on the tall ones); factory europe-west's
"""
from ..europe_west.rooftops import PROGRAMME as EW, flat_block, old_roof, roof_hatch, velux, green_roof


def altbau(it, roof, rng, y, b):
    """Coal-stove flues: 2-4 stacks on each party wall, a few on the flat top, roof windows of the Dachausbau."""
    # (M4 fix round: low stacks, 0.6-1.3 m over the roof, at most 1.6 m long with a cover slab ([rooftops] stack_cap);
    # the first ones rose 1.2-2.3 m with rows of pots, Paris's and London's look)
    old_roof(it, roof, rng, y, b, (1, 3), 0.88, 0.04, 0.45, (1, 2), (0.6, 1.3), (12, 18), (2, 4))
    if not b["shape"] and roof.ok and roof.inner.area >= 120 and rng.random() < 0.07:
        green_roof(it, roof, rng, y, (0.3, 0.6))


def althof(it, roof, rng, y, b):
    old_roof(it, roof, rng, y, b, (1, 2), 0.7, 0.0, 0.2, (0, 2), (0.5, 1.1), None, (1, 3))


def kma(it, roof, rng, y, b):
    if rng.random() < 0.4:
        old_roof(it, roof, rng, y, b, (1, 2), 0.6, 0.0, 0.1, (1, 3), (1.0, 1.8), (14, 20), (1, 3))
    else:
        flat_block(it, roof, rng, y, b, 0.02, 0.05, 0.2)


def nachkrieg(it, roof, rng, y, b):
    flat_block(it, roof, rng, y, b, 0.04, 0.11, 0.4)


def platte(it, roof, rng, y, b):
    flat_block(it, roof, rng, y, b, 0.08, 0.07, 0.25)


def hansa(it, roof, rng, y, b):
    flat_block(it, roof, rng, y, b, 0.02, 0.25, 0.15)


def neubau(it, roof, rng, y, b):
    flat_block(it, roof, rng, y, b, 0.2, 0.33, 0.1)
    if rng.random() < 0.2:
        velux(it, roof, rng, y, int(rng.integers(1, 3)))


def civic(it, roof, rng, y, b):
    EW["civic"](it, roof, rng, y, b)
    if b["shape"] and rng.random() < 0.3:
        roof_hatch(it, roof, rng, y)


PROGRAMME = {"altbau": altbau, "althof": althof, "kma": kma, "nachkrieg": nachkrieg, "platte": platte,
             "hansa": hansa, "neubau": neubau, "beton": civic, "sandstein": civic, "klinker": civic,
             "kirche": EW["civic"], "glass": EW["glass"], "factory": EW["factory"],
             "concretepanel": EW["concretepanel"]}
