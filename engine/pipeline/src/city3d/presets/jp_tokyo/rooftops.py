"""The jp-tokyo preset's rooftop clutter (06c_rooftops): china-south's items in Tokyo's programmes. No solar water
heaters, blue lean-to sheds or plastic tanks on stands (Shenzhen's); Tokyo's roofs carry:
  zakkyo      the stair and lift box (塔屋) in the wall colour, a sectional FRP water tank on a steel stand on some,
              condenser units in rows, a rooftop billboard frame (屋上看板) on one in five
  mansion     china-south's residential towers (lift boxes, panel tanks, the helipad or emergency space on towers
              over 100 m: Tokyo's fire code asks for one), walk-ups: a stair box, a panel tank, condensers
  tiled, granite, depato, government, civic, signs   china-south's commercial (civic: fewer units, tanks)
  glass       china-south's (cooling towers, air handlers, a window-cleaning crane, helipad on the tallest)
  wooden, temple   pitched or small roofs: a condenser now and then
  factory     china-south's
"""
from ..china_south.rooftops import PROGRAMME as CS, ac_units, panel_tank, stair_box
from ...stages.rooftops import BOX, C, M, spot


def billboard(it, roof, rng, y):
    """A rooftop billboard: a painted board on a steel frame along the roof's edge."""
    L, H = rng.uniform(4.0, 8.0), rng.uniform(2.5, 4.5)
    k = int(rng.integers(4))
    p = spot(roof, rng, L, 0.6, "edge", k, 0.2)
    if p is None:
        return False
    col = C[rng.choice(["sign_white", "sign_red", "sign_yellow", "sign_blue", "sign_green", "sign_white"])]
    it.put(roof, BOX, M["steel"], C["steel_dark"], *p, k, y, L, 1.0, 0.5)
    it.put(roof, BOX, M["stair"], col, *p, k, y + 1.0, L, H, 0.25)
    return True


def zakkyo(it, roof, rng, y, b):
    area = roof.inner.area
    if area >= 20 and rng.random() < 0.85:
        stair_box(it, roof, rng, y, b["wall"], (2.2, 3.0, 3.0, 4.5) if area < 80 else (2.6, 3.4, 3.6, 5.0), (2.6, 3.2),
                  "corner", 0.0)
    if area >= 30 and rng.random() < 0.45:
        panel_tank(it, roof, rng, y)
    if rng.random() < 0.7:
        ac_units(it, roof, rng, y, int(rng.integers(2, 7)))
    if area >= 30 and rng.random() < 0.2:
        billboard(it, roof, rng, y)


def mansion(it, roof, rng, y, b):
    if b["room"] is None:
        stair_box(it, roof, rng, y, b["wall"], (2.6, 3.4, 3.6, 5.0), (2.6, 3.1), "edge", 0.0)
        if roof.inner.area >= 60 and rng.random() < 0.5:
            panel_tank(it, roof, rng, y)
        if rng.random() < 0.4:
            ac_units(it, roof, rng, y, int(rng.integers(1, 5)))
        return
    CS["residential"](it, roof, rng, y, b)


def low(it, roof, rng, y, b):
    # (M4 fix round: temples have tiled hip roofs now (jp_tokyo roof_shapes): nothing on a sloped roof)
    if b.get("rise", 0) > 0 or not b.get("roof_ok", True):
        return
    if rng.random() < 0.25:
        ac_units(it, roof, rng, y, int(rng.integers(1, 3)))


PROGRAMME = {**CS, "zakkyo": zakkyo, "mansion": mansion, "tiled": CS["commercial"], "granite": CS["commercial"],
             "depato": CS["commercial"], "signs": CS["commercial"], "government": CS["civic"], "wooden": low,
             "temple": low}
