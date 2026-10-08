"""Tokyo M8 fix round 1 (8 Oct 2026): the viewer's night opt-ins, each off by default (JS-level choices whose default
is the old expression, so the finished cities' shaders are as they were):

- ground.townLights.roads (ground.js: the backdrop's painted major roads lit after dark), ground.lampHeads (the lamp
  heads' glare on a road seen as a line, default 0.35), ground.litAreas (circles of lit pavements and plazas)
- night.masses.far (masses.js: the ring's mean windows times that once sub-pixel)
- night.highExposure (main.js: the night's exposure raised for a high camera)
- night.glows[].lattice (night.js glowMask: a lattice's members lit as lines, the gaps darker)
- night.goldLattice.pale (night.js, lattice.js, facade.js: the gold turning paler with height)
Run: `uv run pytest tests`.
"""
import json
from pathlib import Path

import pytest

VIEWER = Path(__file__).resolve().parents[2] / "viewer"
DEMOS = Path(__file__).resolve().parents[6] / "demos"
FINISHED = ["shenzhen", "nyc", "paris", "london", "berlin"]


def test_viewer_defaults_unchanged():
    ground = (VIEWER / "ground.js").read_text()
    assert "let LAMP_HEADS = 0.35;" in ground and "LAMP_HEADS = ground?.lampHeads ?? 0.35;" in ground
    assert "let TOWN_ROADS = null;" in ground and "if (TOWN_ROADS) {" in ground
    assert "LIT_AREAS = ground?.litAreas?.length ? ground.litAreas : null;" in ground
    # (without litAreas: the old yard lamps' expressions exactly)
    assert ": yardLamps(24, 0.25, 0.035, f01(lot.lessThan(0.88).and(hash2(floor(cellP), 11).lessThan(0.5)))))" in ground
    assert "col.mul(LIT_AREAS ? yardLamps(26, 0.4, 0.04).add(litAreas()) : yardLamps(26, 0.4, 0.04))" in ground
    assert "if (LIT_AREAS) lit = lit.add(" in ground
    masses = (VIEWER / "masses.js").read_text()
    assert "if (MS.far != null) emission = emission.mul(" in masses
    main = (VIEWER / "main.js").read_text()
    assert "const HIGH_EXPOSURE = city.night?.highExposure ?? null;" in main and "if (HIGH_EXPOSURE) {" in main
    night = (VIEWER / "night.js").read_text()
    assert "if (g.lattice && normal) {" in night
    assert "} else g.colour = null;" in night
    lattice = (VIEWER / "lattice.js").read_text()
    assert "(G.colour ? G.colour(positionWorld.y) : night.goldTower)" in lattice
    facade = (VIEWER / "facade.js").read_text()
    assert "(N.goldLattice?.colour ? N.goldLattice.colour(positionWorld.y) : N.goldTower)" in facade


@pytest.mark.parametrize("city", FINISHED)
def test_finished_cities_without_m8f_optins(city):
    p = DEMOS / city / "web" / "city.json"
    if not p.exists():
        pytest.skip(f"no {p}")
    d = json.loads(p.read_text())
    g, n = d.get("ground") or {}, d.get("night") or {}
    assert "roads" not in (g.get("townLights") or {})
    assert "lampHeads" not in g and "litAreas" not in g
    assert "far" not in (n.get("masses") or {})
    assert "highExposure" not in n
    assert "pale" not in (n.get("goldLattice") or {})
    assert not any("lattice" in gl for gl in n.get("glows") or [])


def test_tokyo_settings():
    city = DEMOS / "tokyo" / "web" / "city.json"
    if not city.exists():
        pytest.skip("no Tokyo")
    n = json.loads(city.read_text())["night"]
    assert n["goldLattice"]["pale"][0] < n["goldLattice"]["pale"][1]
    assert any("lattice" in g for g in n["glows"])
    h0, h1, k = n["highExposure"]
    assert h0 < h1 and 1 <= k <= 2.5
