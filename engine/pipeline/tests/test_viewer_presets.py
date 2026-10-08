"""The viewer's facade style presets (engine/viewer/styles/<preset>.json) describe every style the pipeline's regional
preset of the same name can assign (presets/<preset>.toml [facade.styles], with base and replace), so a city's
tiles.json never names a style its viewer preset leaves to the defaults; and the viewer presets' base chains resolve."""
import json
import tomllib
from pathlib import Path

import pytest

PRESETS = Path(__file__).resolve().parents[1] / "src" / "city3d" / "presets"
VIEWER = Path(__file__).resolve().parents[2] / "viewer" / "styles"


def pipeline_styles(name):
    t = tomllib.loads((PRESETS / f"{name}.toml").read_text())
    own = set(t.get("facade", {}).get("styles", {}))
    if t.get("base") and "facade.styles" not in t.get("replace", []):
        own |= pipeline_styles(t["base"])
    return own


def viewer_styles(name, seen=()):
    assert name not in seen, f"viewer preset base loop at {name}"
    d = json.loads((VIEWER / f"{name}.json").read_text())
    styles = dict(d["styles"])
    if d.get("base"):
        styles = {**viewer_styles(d["base"], seen + (name,)), **styles}
    return styles


@pytest.mark.parametrize("name", sorted(p.stem for p in PRESETS.glob("*.toml")))
def test_viewer_preset_covers_pipeline(name):
    assert (VIEWER / f"{name}.json").exists(), f"no viewer preset {name}.json"
    missing = pipeline_styles(name) - set(viewer_styles(name))
    assert not missing, f"{name}: styles the pipeline assigns but the viewer preset doesn't describe: {sorted(missing)}"


def test_viewer_extends_resolve():
    for p in VIEWER.glob("*.json"):
        styles = viewer_styles(p.stem)
        for s, d in styles.items():
            if "extends" in d:
                assert d["extends"] in styles, f"{p.stem}: {s} extends unknown {d['extends']}"


NODE_PRECEDENCE = r"""
const viewer = process.argv[1];
globalThis.window = {};   // (loadCity clears window.__cityJson)
const { loadCity } = await import(viewer + '/city.js');
const { facadeOptions } = await import(viewer + '/styles.js');
const own = { facade: { preset: 'p', roofs: { tones: [[[0.1, 0.1, 0.1], 1]] }, glass: { skyDim: 0.3 } } };
const city = await loadCity('data:application/json,' + encodeURIComponent(JSON.stringify(own)));
const preset = { roofs: { blueSteel: 0.2, blueTone: [0.17, 0.2, 0.24], tones: [[[0.5, 0.5, 0.5], 1]] }, glass: { skyDim: 0.9, grazing: 0.7 } };
const f = facadeOptions(preset, city.facade);
console.log(JSON.stringify({ f, legacy: facadeOptions(preset, { ...city.facade }) }));
"""


def test_facade_options_precedence():
    """engine default < the facade preset's `facade` < city.json's facade (city.js used to merge its defaults over
    city.json first, so a preset's roofs.blueSteel, tones or glass keys the defaults also have never took effect)."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("no node")
    viewer = "file://" + str(VIEWER.parent)
    r = subprocess.run([node, "--input-type=module", "-e", NODE_PRECEDENCE, viewer], capture_output=True, text=True, check=True)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    f = out["f"]
    assert f["roofs"]["blueSteel"] == 0.2                       # the preset over the default 0.45
    assert f["roofs"]["blueTone"] == [0.17, 0.2, 0.24]
    assert f["roofs"]["tones"] == [[[0.1, 0.1, 0.1], 1]]        # city.json over the preset
    assert f["glass"] == {"grazing": 0.7, "skyDim": 0.3, "skyDesat": 0.5, "soft": 0.8, "floor": 0}
    assert "preset" not in f and "styles" not in f and f["probeHeight"] == 110
    # a city object without the layers (built elsewhere): the merged section over the preset, as before
    assert out["legacy"]["roofs"]["blueSteel"] == 0.45
