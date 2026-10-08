"""Hong Kong M7 fix round 1's opt-ins: [trees] carpet (extra classes, smoothed classes), [ground] masses_min_h,
[ground] slopes.areas, and the viewer's trees.carpetBlend; each off by default. Run: `uv run pytest tests`."""
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

VIEWER = Path(__file__).resolve().parents[2] / "viewer"
DEMOS = Path(__file__).resolve().parents[6] / "demos"
FINISHED = ["shenzhen", "nyc", "paris", "london", "berlin"]

CITY = """
name = "hkm7f"
utm_epsg = 32650
[districts]
"Square" = 1
[paths]
data = "data"
"""


def probe(tmp_path, code, extra=""):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "city.toml").write_text(CITY + extra)
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=tmp_path, env=env, capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout.strip().splitlines()[-1]


DEFAULTS = '''
from city3d.stages import trees, masses, ground
print(trees.CARPET_OPTS, trees.CARPET_CLASSES, masses.MIN_H, ground.SLOPE_AREAS)
'''


def test_defaults_off(tmp_path):
    assert probe(tmp_path, DEFAULTS) == \
        "{} ['forest', 'park', 'orchard', 'mangrove', 'scrub'] 0.0 []"


def test_options_read(tmp_path):
    extra = """
[ground]
masses_min_h = 30.0
slopes = { tags = ["natural=cliff"], width = 10.0, areas = ["natural=bare_rock"] }
[trees]
carpet = { extra = ["grass"], smooth = 16.0 }
"""
    assert probe(tmp_path, DEFAULTS, extra) == \
        "{'extra': ['grass'], 'smooth': 16.0} ['forest', 'park', 'orchard', 'mangrove', 'scrub', 'grass'] 30.0 " \
        "['natural=bare_rock']"


SMOOTH = '''
import numpy as np
from city3d.stages import trees
C = trees.C
m = np.full((60, 60), C["forest"], np.uint8)
m[20:23, 20:23] = C["grass"]           # a 24 m grass cell inside the forest: closes
m[40:, 40:] = C["grass"]               # a big grass patch: stays, its corner rounded
m[:10, :] = C["residential"]           # not a carpet class: stays out of it
out = trees.smooth_classes(m, 16.0)
print(int(out[21, 21] == C["forest"]), int(out[50, 50] == C["grass"]), int(out[40, 40] != C["grass"]), int((out[:8] == 0).all()))
'''


def test_smooth_classes(tmp_path):
    assert probe(tmp_path, SMOOTH, '[trees]\ncarpet = { extra = ["grass"], smooth = 16.0 }\n') == "1 1 1 1"


def test_viewer_carpet_blend_gated():
    src = (VIEWER / "trees.js").read_text()
    assert "let FAR = 4500;" in src and "let FAR_FADE = 600;" in src
    assert re.search(r"if \(carpetBlend\) \{", src)
    assert re.search(r"if \(BLEND\) \{", src)
    main = (VIEWER / "main.js").read_text()
    assert "carpetBlend: city.trees.carpetBlend ?? null" in main
    assert "AO_SCENE ? reference('near', 'float', camera) : cameraNear" in main
    assert "masses: city.ground?.townPainted ? false :" in main


@pytest.mark.parametrize("city", FINISHED)
def test_finished_cities_without_m7f_optins(city):
    p = DEMOS / city / "web" / "city.json"
    if not p.exists():
        pytest.skip(f"no {p}")
    d = json.loads(p.read_text())
    assert "carpetBlend" not in (d.get("trees") or {})
    assert "townPainted" not in (d.get("ground") or {})
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from city3d.config import read_city
    cfg = read_city(DEMOS / city / "city.toml")
    assert "masses_min_h" not in cfg.get("ground", {})
    assert "areas" not in (cfg.get("ground", {}).get("slopes") or {})
    assert "carpet" not in cfg.get("trees", {})
