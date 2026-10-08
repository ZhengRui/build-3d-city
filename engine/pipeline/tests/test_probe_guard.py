"""Glass's city probe (engine/viewer/facade.js createCityReflection) is guarded: its faces are drawn into a raw target
and copied through a pass that turns non-finite or negative texels black and holds the rest at PROBE_MAX before the
prefilter, so a garbage fragment (Singapore's night road markings in the 256-pixel faces, b-probe 8 Oct) can't spread
through the GGX levels into black towers and bloom orbs; and a capture that left something out for a pipeline still
compiling is made again (main.js lazily). The guard calls three's PMREMGenerator's private steps, which must exist in
the vendored three the import map pins."""
import re
from pathlib import Path

VIEWER = Path(__file__).resolve().parents[2] / "viewer"


def test_probe_capture_guarded():
    src = (VIEWER / "facade.js").read_text()
    probe = src[src.index("export function createCityReflection"):src.index("export function createFacadeMaterial")]
    assert "gen.fromScene(" not in probe, "the city probe must capture through its guarded fromScene"
    order = [probe.index(s) for s in ("gen._sceneToCubeUV(scene, near, far, raw", "guard.render(renderer)", "gen._applyPMREM(rt)")]
    assert order == sorted(order), "faces into raw, then the guard, then the prefilter"
    assert re.search(r"const PROBE_MAX = (\d+);", src) and int(re.search(r"const PROBE_MAX = (\d+);", src)[1]) >= 200
    assert "NearestFilter" in probe, "the raw faces are read unfiltered (a bad texel never mixes into a good one)"


def test_pmrem_private_steps_vendored():
    three = next((VIEWER / "vendor").glob("three@*/build/three.webgpu.js")).read_text()
    pm = three[three.index("class PMREMGenerator"):]
    for m in ("_setSize(", "_allocateTarget(", "_init(", "_sceneToCubeUV(", "_applyPMREM(", "_cleanup("):
        assert f"\t{m}" in pm, f"three's PMREMGenerator lost {m}"


def test_lazily_recaptures_skipped():
    src = (VIEWER / "main.js").read_text()
    body = src[src.index("function lazily(draw, again = null)"):]
    body = body[:body.index("\n}\n")]
    assert "r.skipped) { again();" in body
