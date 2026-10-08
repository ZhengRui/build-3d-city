"""The viewer's opt-in looks are spelled as the viewer reads them (engine/viewer): a style's patterned skin is one
facade.js draws (lattice, honeycomb, panel, portholes: a misspelt pattern is a plain wall with no warning), a city's
rooftopLook.signGlyphs one rooftops.js knows, and the opt-ins added for Hong Kong's M7 (portholes, roof.wall, CJK sign
glyphs) are built only where a style or city asks for them: no finished city's preset or city.json names them."""
import json
import re
from pathlib import Path

import pytest

VIEWER = Path(__file__).resolve().parents[2] / "viewer"
DEMOS = Path(__file__).resolve().parents[6] / "demos"
PATTERNS = {"lattice", "honeycomb", "panel", "portholes"}
FINISHED = ["shenzhen", "nyc", "paris", "london", "berlin"]
FINISHED_PRESETS = ["china-south", "us-northeast", "europe-west", "uk-london", "de-berlin"]


def styles_of(name):
    d = json.loads((VIEWER / "styles" / f"{name}.json").read_text())
    return d.get("styles", {})


@pytest.mark.parametrize("name", sorted(p.stem for p in (VIEWER / "styles").glob("*.json")))
def test_patterns_known(name):
    for style, d in styles_of(name).items():
        if "pattern" in d:
            assert d["pattern"] in PATTERNS, f"{name}.{style}: pattern {d['pattern']!r} not drawn by facade.js"


def test_facade_draws_every_pattern():
    src = (VIEWER / "facade.js").read_text()
    for p in PATTERNS:
        assert f"d.pattern === '{p}'" in src, f"facade.js has no branch for pattern {p}"


def test_sign_glyphs_option():
    src = (VIEWER / "rooftops.js").read_text()
    assert "look.signGlyphs === 'cjk'" in src
    for city in DEMOS.glob("*/web/city.json"):
        look = json.loads(city.read_text()).get("rooftopLook", {})
        if "signGlyphs" in look:
            assert look["signGlyphs"] in ("cjk", "atlas"), f"{city}: rooftopLook.signGlyphs {look['signGlyphs']!r}"


@pytest.mark.parametrize("name", FINISHED_PRESETS)
def test_finished_presets_without_m7_optins(name):
    for style, d in styles_of(name).items():
        assert d.get("pattern") != "portholes", f"{name}.{style}"
        assert not (d.get("roof") or {}).get("wall"), f"{name}.{style}: roof.wall"


@pytest.mark.parametrize("city", FINISHED)
def test_finished_cities_without_m7_optins(city):
    p = DEMOS / city / "web" / "city.json"
    if not p.exists():
        pytest.skip(f"no {p}")
    d = json.loads(p.read_text())
    assert "signGlyphs" not in d.get("rooftopLook", {})
    assert "woodTint" not in (d.get("ground") or {}).get("cover", {}) if isinstance((d.get("ground") or {}).get("cover"), dict) else True


def test_optins_gated_in_source():
    """Each new branch sits behind its own `uses(...)`/option test, so the shaders of cities without it are unchanged."""
    fac = (VIEWER / "facade.js").read_text()
    assert re.search(r"usePort = uses\(\(d\) => d\.pattern === 'portholes'\)", fac)
    assert re.search(r"if \(usePort\)", fac)
    assert re.search(r"uses\(\(d\) => d\.roof\?\.wall\) \?", fac)


@pytest.mark.parametrize("city", FINISHED)
def test_finished_cities_without_m8_optins(city):
    """Singapore M8's opt-ins (night.corridors, night.arcades, masses.palette) are named by no finished city."""
    p = DEMOS / city / "web" / "city.json"
    if not p.exists():
        pytest.skip(f"no {p}")
    d = json.loads(p.read_text())
    assert "corridors" not in (d.get("night") or {}) and "arcades" not in (d.get("night") or {})
    assert "palette" not in (d.get("masses") or {})


def test_m8_optins_gated_in_source():
    """The corridor and arcade lights are built only when the city asks and a style draws the pattern; the masses'
    palette only when given; night.js leaves both null by default."""
    fac = (VIEWER / "facade.js").read_text()
    assert "corr: night?.corridors && uses((d) => d.corridors) ?" in fac and "if (corr) If(corr" in fac
    assert "arc: night?.arcades && uses((d) => d.fiveFootWay) ?" in fac and "if (arc) If(arc" in fac
    assert "corridors = null, arcades = null" in (VIEWER / "night.js").read_text()
    assert "if (opts.palette) {" in (VIEWER / "masses.js").read_text()


def test_ao_scene_camera_default():
    """The occlusion's far fade with the view camera's near/far: the default for every city since 8 Oct 2026 (an opt-in
    as ao.cameraDepth / ao.sceneCamera before); opt-out ao.cameraDepth false or ?aofix=0. No city opts out."""
    src = (VIEWER / "main.js").read_text()
    assert "const AO_SCENE = params.has('aofix') ? params.get('aofix') !== '0'" in src
    assert ": city.ao?.cameraDepth !== false && city.ao?.sceneCamera !== false;" in src
    assert "AO_SCENE ? reference('near', 'float', camera) : cameraNear" in src
    assert "AO_SCENE ? reference('far', 'float', camera) : cameraFar" in src
    for p in DEMOS.glob("*/web/city.json"):
        ao = json.loads(p.read_text()).get("ao") or {}
        assert ao.get("cameraDepth", True) is not False and ao.get("sceneCamera", True) is not False, p


def test_haze_thin_min_optin():
    src = (VIEWER / "main.js").read_text()
    assert "if (city.haze.thinMin) thinK = thinK.max(city.haze.thinMin);" in src
    for city in FINISHED:
        p = DEMOS / city / "web" / "city.json"
        if p.exists():
            assert "thinMin" not in (json.loads(p.read_text()).get("haze") or {}), city


def test_cover_blend_optin():
    src = (VIEWER / "ground.js").read_text()
    assert "COVER_BLEND = ground?.coverBlend ?? 400;" in src
    assert "smoothstep(float(0), float(COVER_BLEND), edge)" in src
    for city in FINISHED:
        p = DEMOS / city / "web" / "city.json"
        if p.exists():
            assert "coverBlend" not in (json.loads(p.read_text()).get("ground") or {}), city


@pytest.mark.parametrize("city", FINISHED)
def test_finished_cities_without_m8f_optins(city):
    """Singapore M8 fix round 1's opt-ins (night.homes, night.arcades' door/soffit/gradient/spill/upper, night.masses' lamp
    and corridors, ground.apronLights, plazaLamps, townLights.white and farK) are named by no finished city."""
    p = DEMOS / city / "web" / "city.json"
    if not p.exists():
        pytest.skip(f"no {p}")
    d = json.loads(p.read_text())
    night, ground = d.get("night") or {}, d.get("ground") or {}
    assert "homes" not in night
    assert not {"lamp", "corridors"} & set(night.get("masses") or {})
    assert not {"apronLights", "plazaLamps"} & set(ground)
    assert not {"white", "farK"} & set(ground.get("townLights") or {})
    assert "uplight" not in (d.get("trees") or {})


def test_m8f_optins_gated_in_source():
    """Each M8 fix round 1 look is built only when its option is given; without it the old expression, constant for
    constant (finished cities' shaders byte-identical)."""
    fac = (VIEWER / "facade.js").read_text()
    assert "const farN = HOM?.far ? smoothstep(float(HOM.far[0]), float(HOM.far[1]), max(wx, wy)) : max(far, smoothstep(float(0.08), float(0.28), max(wx, wy)));" in fac
    assert "HOM?.room ? mix(float(HOM.room[0]), float(HOM.room[1]), bh) : mix(float(0.22), float(1.5), bh.mul(bh))" in fac
    assert "float(HOM?.curtains ?? 0.3)" in fac
    assert "shut: night?.arcades?.upper && uses((d) => d.shophouseFront) ?" in fac and "if (shut) If(shut" in fac
    assert "const arcShops = arc && N.arcades.shops != null ?" in fac and "return arcShops ? o.mul(arcShops) : o;" in fac
    assert "door.mul(A.door ?? 0.9).add(soffit.mul(A.soffit ?? 0.45)).add(spill.mul(A.spill ?? 0.08))" in fac
    assert "corridors = null, arcades = null, homes = null" in (VIEWER / "night.js").read_text()
    mas = (VIEWER / "masses.js").read_text()
    assert "MS.lamp ? vec3(...MS.lamp) : vec3(1, 0.78, 0.55)" in mas and "if (MS.corridors) {" in mas
    gr = (VIEWER / "ground.js").read_text()
    assert "if (night && APRON) {" in gr and "if (PLAZA_LAMPS) {" in gr
    assert "TOWN_WHITE ? vec3(...TOWN_WHITE) : LED" in gr and "if (TOWN_WHITE) col = mix(" in gr
    assert "TOWN_FAR_K = ground?.townLights?.farK ?? 1.6;" in gr
    assert "if (UPLIGHT) {" in (VIEWER / "trees.js").read_text()
    assert "uplight: city.trees.uplight ? {" in (VIEWER / "main.js").read_text()


@pytest.mark.parametrize("city", FINISHED)
def test_finished_cities_without_hk_m8_optins(city):
    """Hong Kong M8's opt-ins (rooftopLook.signSpill, ground.junctionPools) are named by no finished city."""
    p = DEMOS / city / "web" / "city.json"
    if not p.exists():
        pytest.skip(f"no {p}")
    d = json.loads(p.read_text())
    assert "signSpill" not in (d.get("rooftopLook") or {})
    assert "junctionPools" not in (d.get("ground") or {})
    assert "spread" not in ((d.get("night") or {}).get("homes") or {})
    assert "max" not in (d.get("glow") or {})


def test_hk_m8_optins_gated_in_source():
    """The signs' street spill is built only with rooftopLook.signSpill, the street signs and the night (no mesh, no
    shader otherwise); the junctions' pools only with ground.junctionPools (the old junction expression unchanged)."""
    roof = (VIEWER / "rooftops.js").read_text()
    assert "if (look.signSpill && SIGN >= 0 && night && terrain) {" in roof
    assert "if (spill) spill.visible = spill.userData.n > 0 && night.lights.value > 0;" in roof
    assert "return { group, update, stats, meshes, index, tiles, prepareParapets, spill };" in roof
    assert "if (rooftops?.spill?.userData.sa) {" in (VIEWER / "main.js").read_text()
    gr = (VIEWER / "ground.js").read_text()
    assert "let junction = regionLamp(float(1), float(0), sodium).mul(STREET * 0.55);\n    if (JUNCTION_POOLS) {" in gr
    assert "JUNCTION_POOLS = ground?.junctionPools ? { cell: 22, h: 8, k: 1, ...ground.junctionPools } : null;" in gr


def test_hk_m8_homes_spread_and_glow_max_gated():
    """night.homes.spread and glow.max change nothing unless given (the old constants otherwise)."""
    fac = (VIEWER / "facade.js").read_text()
    assert "V.bShare.mul(HSP != null ? 0.8 * HSP : 0.8)" in fac
    assert "mul(HSP != null || WSP != null ? sel(fl, float(3.46 * (HSP ?? 1)), float(3.46 * (WSP ?? 1))) : 3.46)" in fac
    main = (VIEWER / "main.js").read_text()
    assert "const GLOW_MAX = city.glow?.max ?? null;" in main
    assert "if (GLOW_MAX != null) c = c.min(vec4(GLOW_MAX, GLOW_MAX, GLOW_MAX, GLOW_MAX));" in main
def test_m9_branches_opt_in():
    """Singapore M9: the on-wall patterns' and the building glows' branches are off by default (the finished cities'
    shaders unchanged) and only Singapore's city.json turns them on."""
    fac = (VIEWER / "facade.js").read_text()
    assert "bayFade = null, patternBranch = false," in fac and "if (patternBranch) {" in fac
    assert "if (N.glowBranch && bGlows.length) {" in fac
    assert "glows = [], glowBranch = false, carSpots" in (VIEWER / "night.js").read_text()
    for city in FINISHED:   # (the cities' files exist only in the project that built them: skipped standalone)
        p = DEMOS / city / "web" / "city.json"
        if not p.exists():
            continue
        cj = json.loads(p.read_text())
        assert not (cj.get("facade") or {}).get("patternBranch"), city
        assert not (cj.get("night") or {}).get("glowBranch"), city
    for name in FINISHED_PRESETS:
        assert "patternBranch" not in json.loads((VIEWER / "styles" / f"{name}.json").read_text()).get("facade", {}), name
    p = DEMOS / "singapore" / "web" / "city.json"
    if p.exists():
        sg = json.loads(p.read_text())
        assert sg["facade"]["patternBranch"] is True and sg["night"]["glowBranch"] is True


@pytest.mark.parametrize("city", FINISHED)
def test_finished_cities_without_hk_m8f_optins(city):
    """Hong Kong M8 fix round 1's opt-ins (night.homes.glitter, night.windows.spread, night.boards, signGlyphs "atlas")
    are named by no finished city."""
    p = DEMOS / city / "web" / "city.json"
    if not p.exists():
        pytest.skip(f"no {p}")
    d = json.loads(p.read_text())
    night = d.get("night") or {}
    assert "glitter" not in (night.get("homes") or {})
    assert "spread" not in (night.get("windows") or {})
    assert "boards" not in night
    assert (d.get("rooftopLook") or {}).get("signGlyphs") != "atlas"
    wn = (d.get("water") or {}).get("night") or {}
    assert "zenith" not in wn and "steep" not in wn


def test_hk_m8f_optins_gated_in_source():
    """Each is built only when asked for: the old expressions stand otherwise."""
    fac = (VIEWER / "facade.js").read_text()
    assert "if (near !== true && HOM?.glitter) {" in fac
    assert "sqrt(floorsLit.mul(float(1).sub(floorsLit))).mul(WSP != null ? 2.84 * WSP : 2.84)" in fac
    assert "const boardOn = B ? varying(" in fac
    assert "if (B) If(boardOn.greaterThan(0.5)" in fac
    assert "boards,\n  };" in (VIEWER / "night.js").read_text()
    roof = (VIEWER / "rooftops.js").read_text()
    assert "if (look.signGlyphs === 'atlas') {" in roof
    wat = (VIEWER / "water.js").read_text()
    assert "const kneeN = ST ? mix(TK ? knee0 : float(NIGHT.knee), ST.knee != null ? float(ST.knee) : knee0, steepT) : knee0;" in wat
    assert "const gainN = ST ? mix(TK ? gain0 : float(NIGHT.gain), ST.gain != null ? float(ST.gain) : gain0, steepT) : gain0;" in wat
    assert "const skyN = NIGHT.zenith != null ? mix(" in wat and ": skyN0;" in wat
def test_m9f_scheduling_and_slider_resolution():
    """Singapore M9 fix round 1: the held change of light's queue kept full on WebGL 2 and the time slider's rest rule
    are scheduling only (on by default, each with a switch back: ?heldfill=0, ?timerest=0); the slider's own
    resolution is opt-in (time.sliderResolution, null by default) and no finished city sets it."""
    main = (VIEWER / "main.js").read_text()
    assert "const HELD_FILL = GL_PARALLEL && params.get('heldfill') !== '0';" in main
    assert "const TIME_REST = params.get('timerest') !== '0', TIME_REST_MS = 250;" in main
    assert "city.time.sliderResolution || null" in main
    assert "sliderResolution: null" in (VIEWER / "city.js").read_text()
    for city in FINISHED:
        p = DEMOS / city / "web" / "city.json"
        if p.exists():
            assert (json.loads(p.read_text()).get("time") or {}).get("sliderResolution") is None, city


def test_animation_webgpu_only_optin():
    """Tokyo M9: animation.webgpuOnly (gate and full on WebGPU only, the defaults on WebGL 2) is off by default and
    set by no finished city."""
    assert "webgpuOnly: false" in (VIEWER / "city.js").read_text()
    src = (VIEWER / "main.js").read_text()
    assert "city.animation.webgpuOnly && IS_GL ? { ...city.animation, gate: 'settled', full: false }" in src
    assert "ANIM_CFG.gate" in src and "ANIM_CFG.full" in src
    for city in FINISHED:
        p = DEMOS / city / "web" / "city.json"
        if p.exists():
            assert not (json.loads(p.read_text()).get("animation") or {}).get("webgpuOnly"), city


def test_m9_webgl_regressions():
    """Singapore M9 fix (WebGL 2 light-change regressions): the held change of light's first frame drawn at the next
    animation frame after its last round (scheduling only, on by default, ?heldnext=0: as before); the slider's rest
    rule checked before the moving frames' branch."""
    main = (VIEWER / "main.js").read_text()
    assert "const HELD_NEXT = params.get('heldnext') !== '0';" in main
    assert "if (!HELD_NEXT) return false;" in main
    assert main.index("if (dirty && hold !== null && TIME_REST && now - timeDragAt < TIME_REST_MS)") < main.index(
        "if (dirty && viewDirty) {\n")
