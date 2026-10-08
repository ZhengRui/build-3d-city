// Procedural building facades (TSL): windows, floors, glass curtain walls, balconies, shopfronts,
// weathering and roofs, plus the landmark styles (stainless fins, spandrel bands, steel lattice,
// honeycomb skin, metal panels), from the per-vertex data written by 06_tiles.py:
//   color  rgb: wall colour (glass tint for curtain walls); a: bay module / index.moduleMax (0 = default)
//   uv     (distance along the wall run, run length), stored as 0..1 of index.uvRange.uv
//   uv1    (style id + seed, building height), stored as 0..1 of index.uvRange.fac; landmark rows
//          replace the random seed with a style parameter (fin width, share of solid panels...)
//   uv2    (base, 0): the ground the building stands on, as 0..1 of index.uvRange.base
// Heights come from the world position less the base and roofs are told apart by their normal.
//
// Glass reflects the city itself: createCityReflection captures the scene around the orbit target into
// a prefiltered cube map (PMREM) whenever the view settles somewhere new or the sun moves, and glass looks
// it up parallax-corrected (the reflected world is assumed a few hundred metres away, or on the ground),
// so towers mirror their neighbours, the streets below and the sky with its clouds. Curtain walls are
// shaded as coated glass over dark interiors and spandrel panels: Fresnel from each pane's own, slightly
// tilted and pillowed normal (the reflections break up pane by pane and floor by floor), per-pane
// reflectance and blinds, box-filtered mullion, spandrel and refuge-floor patterns that average out
// instead of shimmering, and a variation that moves to ever larger groups of panes as the panes shrink
// below a pixel, so a distant tower keeps a mottled mirror rather than turning into a flat tint.
//
// After dark (the uniforms from night.js) rooms light up: per window, per flat or per office zone, a
// share that depends on the kind of building and the hour, in warm, neutral or cool white, some behind
// curtains; shopfronts and their signs on the ground floors, street light washing the lower walls, lit
// crowns and fins on some towers, red obstruction lights on the tallest, the city's glow on the roofs. A
// hierarchy like the glass's keeps it from shimmering: rooms smaller than a few pixels are lit in ever
// larger groups, each at its own share, so towers fade into a soft, floor-banded glow.
import * as THREE from 'three/webgpu';
import { ATLAS } from './billboards.js';
import { glowMask } from './night.js';
// (main.js takes the atlas maker from here: imported again with its own query it was a second copy of the module)
export { makeBillboardAtlas } from './billboards.js';
import {
  vec2, vec3, vec4, uv, vertexColor, positionWorld, normalWorldGeometry, cameraPosition, cameraViewMatrix,
  pmremTexture, fwidth, hash, select, mix, smoothstep, max, min, abs, floor, fract, round, pow, mod, dot, clamp,
  log2, exp2, exp, sqrt, atan, normalize, reflect as reflectDir, length, uniform, cos, sin, varying, Fn, If, texture, bool,
  diffuseColor, floatBitsToUint, uint,
} from 'three/tsl';

// the core features and the node helpers (facade/core.js), with this module's own query (main.js imports the engine
// with one, so a new version is fetched anew)
const { float, pick, f01, sel, band, lines, stripe, h1, hash2, rgb, shareOf, bandAt, rusticJoints, brickRes, brickCourses,
  corniceShadow, shopfront: shopfrontOf, windowCoords } = await import(`./facade/core.js${new URL(import.meta.url).search}`);
const { roofLook } = await import(`./facade/roofs.js${new URL(import.meta.url).search}`);
// the pattern library (facade/patterns.js): patterns named by architecture, each built when a style lists it
const P = await import(`./facade/patterns.js${new URL(import.meta.url).search}`);
const { windowBars, shopWindowBars } = await import(`./facade/core.js${new URL(import.meta.url).search}`);

// ---------------------------------------------------------------- the city reflection probe
// The scene seen from one point above the orbit target (CITY_PROBE_H metres up, or city.json's
// facade.probeHeight: higher among skyscrapers, where a low probe sees little but shaded walls; higher
// still when the target is), rendered into a cube and prefiltered by a PMREMGenerator of its own. Two targets are used in turn:
// glass samples the last capture while the next one is drawn (a target can't be read and written at once).
// Before the first capture glass samples the sky map it is given.
// Cost: six 256 x 256 views of the scene (tiles within CITY_REACH, trees left out) plus the PMREM blur,
// only when update() finds the probe stale: the view settled over 300 m (or a fifth of the view distance)
// from the last capture, the sun moved, or markStale() was called (tiles finished loading).
// Options (city.json facade.probe, main.js; all off by default, as New York and Shenzhen were measured):
// reach: the tiles drawn into the faces, metres from the probe (by default the tile's centre within CITY_REACH; with
// nearest, the tile's nearest point, so that a 4 km merged block the probe stands in is never left out)
const CITY_PROBE_H = 110, CITY_REACH = 3500, CITY_SIZE = 256;
// The faces are drawn into a raw target of their own and copied into the capture through a guard before they are
// prefiltered: a texel with a channel that is not finite or is negative becomes black, and the rest is held at
// PROBE_MAX (linear; the brightest texel of an ordinary capture was 130, Singapore at 18:30). After dark the road
// markings' lit shader gives a few of their sub-pixel fragments in the 256-pixel faces garbage colours, different at
// each render of the same scene (NaN, +-65504, one channel in the thousands; Singapore's Marina Bay probe, b-probe
// 8 Oct; the main view's pixels showed none). Unguarded, the prefilter (GGX) spread each into thousands of texels of
// every rougher level, and glass looked them up: black walls with a white band, red, blue and white bloom orbs on tower
// tops; and glass in the next capture mirrored this one's, so the bad values went on from capture to capture (the facade's
// soft shoulder x / (0.8x + 1) of a negative near -1.25 is huge), cleared only by two clean captures in a row
const PROBE_MAX = 256;
const finite1 = (x) => floatBitsToUint(x).bitAnd(uint(0x7f800000)).notEqual(uint(0x7f800000));
export function createCityReflection(renderer, skyEnv, { height = CITY_PROBE_H, reach = CITY_REACH, nearest = false } = {}) {
  const gen = new THREE.PMREMGenerator(renderer);
  // the raw faces (nearest sampling: a guarded texel never mixes with a bad neighbour) and the guard's pass
  let raw = null;
  const rawTex = texture(null);
  const guard = new THREE.QuadMesh(new THREE.NodeMaterial());
  guard.material.name = 'probeGuard';
  guard.material.depthTest = guard.material.depthWrite = false;
  guard.material.blending = THREE.NoBlending;
  guard.material.fragmentNode = Fn(() => {
    const c = rawTex.rgb;
    const ok = finite1(c.r).and(finite1(c.g)).and(finite1(c.b)).and(min(min(c.r, c.g), c.b).greaterThan(-1e-3));
    return vec4(select(ok, min(max(c, vec3(0, 0, 0)), vec3(PROBE_MAX, PROBE_MAX, PROBE_MAX)), vec3(0, 0, 0)), 1);
  })();
  // three's PMREMGenerator.fromScene (r186, pinned by the import map) with the guard between the faces and the prefilter
  function fromScene(scene, near, far, size, position, rt) {
    gen._setSize(size);
    const oldTarget = renderer.getRenderTarget(), oldFace = renderer.getActiveCubeFace(), oldLevel = renderer.getActiveMipmapLevel();
    rt ??= gen._allocateTarget(false);
    if (!raw) {
      raw = gen._allocateTarget(true);
      raw.texture.minFilter = raw.texture.magFilter = THREE.NearestFilter;
      raw.texture.name = 'probe.raw';
      rawTex.value = raw.texture;
    }
    gen._init(rt);
    gen._sceneToCubeUV(scene, near, far, raw, position);
    rt.viewport.set(0, 0, rt.width, rt.height);
    rt.scissor.set(0, 0, rt.width, rt.height);
    renderer.setRenderTarget(rt);
    guard.render(renderer);
    gen._applyPMREM(rt);
    gen._cleanup(rt);
    raw.scissorTest = false;
    raw.viewport.set(0, 0, raw.width, raw.height);
    renderer.setRenderTarget(oldTarget, oldFace, oldLevel);
    return rt;
  }
  const targets = [null, null];
  const nodes = [];                                  // pmremTexture nodes to point at each new capture
  const center = uniform(new THREE.Vector3(0, height, 0));
  const captured = uniform(0);                      // 1 once the city has been captured
  let current = skyEnv, next = 0, stale = true;
  const at = new THREE.Vector3(Infinity, 0, 0), pos = new THREE.Vector3();
  const hidden = [];
  let spare = null;                                 // prepare()'s own target
  const probePosition = (target, ground) => pos.set(target.x, Math.max(ground + height, target.y * 0.8 + 30), target.z);
  // the scene seen from pos into rt (made if null); returns the target
  // lighten(pos): called once the hidden objects are hidden, returns what undoes it (main.js: facade.probe.lean's ground)
  function capture(scene, rt, { hide = [], sky = null, fogDensity = null, before = null, lighten = null }) {
    before?.();
    hidden.length = 0;
    for (const o of hide) if (o.visible) hidden.push(o);
    for (const o of scene.children) {
      const t = o.userData.tile;
      if (t && o.visible && !probe.inReach(t.x, t.z, t.x + t.size, t.z + t.size, pos)) hidden.push(o);
    }
    for (const o of hidden) o.visible = false;
    const undo = lighten?.(pos);
    const disc = sky?.showSunDisc.value, density = scene.fog?.density;
    if (sky) sky.showSunDisc.value = 0;
    if (scene.fog && fogDensity !== null) scene.fog.density = fogDensity;
    // three's PMREMGenerator (r186) renders every capture with one camera shared by all generators, setting its
    // near and far without rebuilding its projection; the renderer rebuilds it once, at the camera's first render
    // (on WebGPU, when it switches the camera's coordinate system), with whatever near and far were set then: the
    // sky map's 100 m. Everything farther was clipped away, glass mirrored bare sky, and towers wore a light-blue
    // coat on WebGPU (on WebGL 2 the projection kept its default 2 km). So the projection is rebuilt per render.
    const render = renderer.render, own = Object.prototype.hasOwnProperty.call(renderer, 'render');
    renderer.render = function (s, cam) { if (cam.isPerspectiveCamera) cam.updateProjectionMatrix(); return render.call(this, s, cam); };
    try {
      rt = fromScene(scene, 1, 120000, CITY_SIZE, pos, rt);
    } finally {
      if (own) renderer.render = render; else delete renderer.render;
    }
    if (sky) sky.showSunDisc.value = disc;
    if (scene.fog) scene.fog.density = density;
    undo?.();
    for (const o of hidden) o.visible = true;
    return rt;
  }
  const probe = {
    center, captured, captures: 0, lastMs: 0,
    // where the next capture for this orbit target stands, its faces' size in pixels (six 90° views) and the reach of
    // the tiles it draws
    positionFor: (target, ground = 0, out = new THREE.Vector3()) =>
      out.set(target.x, Math.max(ground + height, target.y * 0.8 + 30), target.z),
    size: CITY_SIZE, reach,
    // whether the rectangle [x0, x1] x [z0, z1] (a tile) is drawn into a capture from p
    // (reach and nearest may be changed later, for comparisons)
    nearest,
    inReach: (x0, z0, x1, z1, p) => (probe.nearest
      ? Math.hypot(Math.max(x0 - p.x, 0, p.x - x1), Math.max(z0 - p.z, 0, p.z - z1))
      : Math.hypot((x0 + x1) / 2 - p.x, (z0 + z1) / 2 - p.z)) <= probe.reach,
    // no capture to sample: glass reflects the sky map (and its dim stand-in for the city below the horizon)
    get empty() { return captured.value === 0; },
    // the render target glass samples now (null before the first capture or after a drop: the sky map), for checks
    get target() { return captured.value === 0 ? null : targets[next ^ 1]; },
    // the last capture's faces as drawn, before the guard (for checks)
    get raw() { return raw; },
    // the probe's radiance towards dir (need not be normalised), blurred as for this roughness
    sample(dir, roughness) {
      const n = pmremTexture(current, dir, roughness);
      nodes.push(n);
      return n;
    },
    markStale() { stale = true; },
    // call on settled frames, before rendering the view. target: the orbit target; viewDistance: camera to
    // target; hide: objects to leave out (trees); sky: the SkyMesh, whose sun disc is left out (the sun
    // light's own specular draws the glint); fogDensity: the haze at ground level; before(): called just
    // before capturing (main.js switches the water's mirror off: it is drawn for the main camera only);
    // ground: the ground's height under the target (the probe stays CITY_PROBE_H above it, out of the hills).
    // Returns true when it captured.
    update(scene, target, viewDistance, { ground = 0, ...options } = {}) {
      if (!probe.due(target, viewDistance, ground)) return false;
      const t0 = performance.now();
      const i = next;
      next ^= 1;
      targets[i] = capture(scene, targets[i], options);
      current = targets[i].texture;
      for (const n of nodes) n.value = current;
      center.value.copy(pos);
      captured.value = 1;
      at.copy(pos);
      stale = false;
      probe.captures++;
      probe.lastMs = performance.now() - t0;          // CPU side only (for the console)
      return true;
    },
    // whether update() would capture now: stale, or the probe's place moved on from the last capture's
    due(target, viewDistance, ground = 0) {
      probePosition(target, ground);
      return stale || Math.hypot(pos.x - at.x, pos.z - at.z) > Math.max(300, viewDistance * 0.2)
        || Math.abs(pos.y - at.y) > 0.3 * at.y;
    },
    // a capture that was due left out (facade.probe.glassOnly: no glass in view): the last capture is kept while it
    // still fits (only the view moved, by no more than the reach), else dropped, glass falling back to the sky map
    // until the next capture (a capture in another light, or with tiles missing, or of another place, would
    // mirror the wrong city)
    skip(target, ground = 0) {
      probePosition(target, ground);
      if (captured.value === 0 || (!stale && Math.hypot(pos.x - at.x, pos.z - at.z) <= probe.reach)) return;
      current = skyEnv;
      for (const n of nodes) n.value = current;
      captured.value = 0;
      at.set(Infinity, 0, 0);
      stale = true;
      probe.dropped++;
    },
    dropped: 0,
    // the same capture into a target of its own, the probe left as it is: for main.js to have its shaders
    // compiled without drawing anything (compileOnly)
    prepare(scene, target, { ground = 0, ...options } = {}) {
      probePosition(target, ground);
      spare = capture(scene, spare, options);
    },
  };
  return probe;
}

// env: a PMREM of the sky (glass falls back to it until the city has been captured); city: the probe
// from createCityReflection, or null for sky-only reflections. The reflection is added as emission
// (so walls and roofs keep the scene's plain sky light, not the environment's much stronger diffuse
// term); reflectStrength scales it (the menu's reflections slider), 1 = physical.
// night: the uniforms from night.js (createNight().u), or null for a city that never lights up.
// look: city.json's facade section over the preset's (styles.js resolveStyles: its `facade`; city.js has the defaults):
// styles (the resolved style data by name: bay widths, window boxes, shop shares, ac units, groups and features; see
// styles.js and styles/*.json), refugeShare (towers over 150 m with refuge floors), glass (the glass's live look,
// userData.tune), windowF0 (plain windows' reflectance head on), shopfront ({ box: [xlo, ylo, yhi] of the ground
// floor's shop windows, doorEvery: a door in every n-th bay }), bayFade ([from, to]: the 'bays' detail branch's fade by
// the bays' size on screen, default [0.12, 0.35]), billboardBranch (the signs style's boards in a branch of their own,
// default false), patternBranch (the on-wall patterns, paintBands to shophouseFront, each in a branch of its own, default
// false: inline, every wall pixel paying for all of them); billboards: the signs style's art (billboards.js
// makeBillboardAtlas); nightSigns ({ screens, boards }, default 4 and 2.2; Tokyo M8: Shibuya's screens and the signboards
// had bloomed to white): the brightness after dark of the signs style's billboards and screens and of the vertical signboards.
export function createFacadeMaterial({ uvRange, floor: nominalFloor, styles, moduleMax }, env, reflectStrength = 1, city = null, night = null,
  { styles: styleData = {}, refugeShare = 0.55, glass: glassLook = {}, billboards = null, roofs = {}, streetLight = null,
    shopSeed = false, windowF0 = 0.05, shopfront = {}, farFade = [0.12, 0.35], bayFade = null, patternBranch = false,
    billboardBranch = false, nightSigns = null } = {}) {
  // glass options read here, not live uniforms (constants: a city without them gets the shader it had): silverFrom
  // and silverTo, the tint luminance (linear) over which curtain-wall glass reads as coated silver (silverDesat: its body
  // that much greyer than the tint, 0..1); variety: per-tower
  // mullion rhythms and module widths on the plain glass style (London M4 fix round: every tower one grid)
  // nearSoft [from, to, rough, fade] (Hong Kong M4 fix round 1): glass close to the camera, under `from` m and fading
  // out by `to`, looks its reflection up `rough` rougher and reflects `fade` less: the probe's cube faces are coarse for
  // a wall seen from a few tens of metres, and its mirrored towers broke into stepped, pixelated blocks
  const { silverFrom = 0.18, silverTo = 0.4, silverDesat = 0, variety = false, nearSoft = null, ...glass } = glassLook;
  // physical: its specular colour lets the coated glass's sun glint be as strong as its reflections
  const mat = new THREE.MeshPhysicalNodeMaterial({ roughness: 0.85, metalness: 0 });
  const ID = Object.fromEntries(styles.map((name, i) => [name, i]));
  const NONE = bool(false);
  // the style data in STYLES order (06_tiles.py); a style no preset knows: {}, all defaults ('crowned' takes 'stone''s
  // entries: `extends`, styles.js)
  const SD = styles.map((name) => styleData[name] ?? {});
  // per-style values in STYLES order, for pick(): get(style data) or the default
  const perStyle = (get, dflt) => SD.map((d) => get(d) ?? dflt);
  // the styles whose data passes test, and whether there are any: a feature is built into the shader only when one
  // of the city's styles uses it
  const users = (test) => styles.filter((name, i) => test(SD[i]));
  const uses = (test) => users(test).length > 0;

  const run = uv(0).mul(vec2(uvRange.uv[0], uvRange.uv[1]));
  const fac = uv(1).mul(vec2(uvRange.fac[0], uvRange.fac[1]));
  const code = fac.x.add(0.0005);
  const style = floor(code);
  const seed = fract(code).div(0.999);
  const height = fac.y;
  const s = run.x, runLen = max(run.y, 0.01);           // roofs have no wall run: keep 0/0 out of the mixes
  // heights from the building's base (uv2: the ground it stands on; its walls reach a little below)
  const base = uv(2).x.mul(uvRange.base[0]);
  const y = positionWorld.y.sub(base);
  const isRoof = normalWorldGeometry.y.greaterThan(0.9);
  const wallColor = vertexColor().rgb;
  const moduleM = vertexColor().a.mul(moduleMax);
  // roofs (06_tiles roof_shapes; 0 in cities without): uv2.y = the roof's rise (m) + 8 x its material (1 zinc or
  // slate, 2 tile, 3 flat mineral, 0 unknown). A building with a rise has its walls, floors and cornice up to the
  // eaves, then a mansard's steep brisis (with dormers) or a pitched roof; its walls above the eaves are party gables
  // (a city without roof codes, New York or Shenzhen, gets constants here. Tiles packed before roof codes have uv2.y's
  // range 1 and carry 0 in it; with roof codes the range is 32. Tested `> 0`, New York and Shenzhen ran the mansards'
  // brisis, dormers and seams in every building pixel for nothing: WebGL 2 moving frames at Downtown Brooklyn
  // 128 -> 103 ms on the Iris Xe once left out)
  const roofCodes = (uvRange.base[1] ?? 0) > 1;
  const roofCode = uv(2).y.mul(uvRange.base[1] ?? 0).add(0.001);
  const roofMat = roofCodes ? floor(roofCode.div(8)) : float(0);
  const roofRise = max(roofCode.sub(roofMat.mul(8)).sub(0.001), 0);
  const hasRoof = roofCodes ? roofRise.greaterThan(0.05) : NONE;
  const wallH = roofCodes ? sel(hasRoof, height.sub(roofRise), height) : height;
  const slopeRoof = roofCodes ? hasRoof.and(isRoof.not()).and(normalWorldGeometry.y.greaterThan(0.15)) : NONE;
  const brisis = slopeRoof.and(normalWorldGeometry.y.lessThan(0.55));
  // (the walls' top edge, in every city: with positions quantized to a few cm the top centimetres of a wall can lie above
  // the 2 cm, its cornice and windows off there, as New York's and Shenzhen's walls have been drawn since roof codes)
  const onWall = y.lessThan(wallH.add(0.02));

  // a style this city doesn't have is never matched: a constant false (a comparison with an undefined id would be
  // `null` in WGSL), which the GPU driver's compiler folds away with everything that only that style uses
  // (a fresh comparison per test: shared, each would become a variable of its own; the node count is kept down by the
  // shared constants instead, facade/core.js float)
  const is = (name) => (ID[name] === undefined ? NONE : style.equal(ID[name]));
  // the named styles as one test (isOf: the test of one style, e.g. on a branch's copy of the style id); none: false
  const inStyles = (names, isOf = is) => names.reduce((acc, name) => (acc ? acc.or(isOf(name)) : isOf(name)), null) ?? NONE;
  // the styles whose data passes test
  const where = (test, isOf = is) => inStyles(users(test), isOf);
  // a per-style value as a select per value (its users together), the default for the styles without one; a constant
  // when no style has its own
  const byValue = (get, dflt, node = float, isOf = is) => {
    const groups = new Map();
    SD.forEach((d, i) => {
      const v = get(d), k = JSON.stringify(v);
      if (v === undefined || v === null || k === JSON.stringify(dflt)) return;
      if (!groups.has(k)) groups.set(k, { v, names: [] });
      groups.get(k).names.push(styles[i]);
    });
    return [...groups.values()].reduceRight((r, g) => sel(inStyles(g.names, isOf), node(g.v), r), node(dflt));
  };
  // the rustication's test over its users (styles.js rustication): per group of the same `on` (the building's stucco
  // ground floor or stucco front, a node in `on`) or else the styles themselves, on the lowest `rows` floors (a select
  // where they differ), not behind shops (notShops)
  const rusticTest = (names, { row, notGround, isOf, on = {} }) => {
    const groups = new Map();
    for (const n of names) {
      const r = styleData[n].rustication, k = `${r.on ?? ''}|${!!r.notShops}`;
      if (!groups.has(k)) groups.set(k, { on: r.on, notShops: !!r.notShops, names: [] });
      groups.get(k).names.push(n);
    }
    return [...groups.values()].map((g) => {
      let t = g.on ? on[g.on] : inStyles(g.names, isOf);
      const rows = [...new Set(g.names.map((n) => styleData[n].rustication.rows).filter((r) => r))];
      if (rows.length === 1) t = t.and(row.lessThan(rows[0] - 0.5));
      else if (rows.length > 1) {
        const first = styleData[g.names[0]].rustication.rows;
        const lim = g.names.filter((n) => styleData[n].rustication.rows !== first).reduceRight((r, n) =>
          sel(isOf(n), float(styleData[n].rustication.rows - 0.5), r), float(first - 0.5));
        if (g.notShops) return t.and(notGround).and(row.lessThan(lim));
        t = t.and(row.lessThan(lim));
      }
      return g.notShops ? t.and(notGround) : t;
    }).reduce((a, b) => a.or(b));
  };
  // (the night's kinds of building, styles.js night: home, village, mall, factory, none; offices are the curtain walls,
  // the rest civic. Villages and factories are also their day look: grime, dark village roofs, steel factory roofs)
  const nightKind = (k) => where((d) => d.night === k);
  const isVillage = nightKind('village'), isFactory = nightKind('factory'), isPlain = is('plain');
  // the masts and spires of towers (steel, no windows)
  const isSpire = is('spire');
  // the wall-detail slots (styles.js `fade`): a style's wall features are drawn on the wall itself (no fade: Paris's
  // rustication, floor bands, surrounds, quoins, panel spandrels), or in a branch only those walls pay for, built from
  // copies of its inputs: 'none' everywhere on the wall (London's terraces), 'bays' only where the bays are resolved
  // (Berlin's fronts). Every feature is built only when one of the city's styles (in that slot) lists it
  const onTop = (d) => !d.fade, fadeNone = (d) => d.fade === 'none', fadeBays = (d) => d.fade === 'bays';
  const anyNone = uses(fadeNone), anyBays = uses(fadeBays);
  // the ground floor's shops (the preset's facade.shopfront): boards, letters, pilasters, riser, glazing, interior, awnings
  const SF = shopfront;
  // Haussmann's and the palaces' cut stone: guard rails across the French windows
  const isGuarded = where((d) => d.guardRails);
  // homes: lit as homes after dark (city.json night.homeStyles too)
  const isHome = where((d) => d.night === 'home');
  // floodlit: statues and monuments (no windows); after dark washed by floodlights, a style parameter of 0.98
  // or more glowing (a torch's flame)
  const isFlood = is('floodlit');
  // walls covered in billboards and LED screens up to a band height (Times Square), glass above
  const isSigns = where((d) => d.billboards);
  // punched windows, cornices
  const isMasonry = where((d) => d.masonry);
  // monuments (styles.js `monument`: the landmark kinds, see below)
  const isMon = where((d) => d.monument);
  // piers: fins in glazed terracotta instead of stainless (Steinway Tower)
  const isPiers = is('piers');
  const isFins = is('fins').or(isPiers), isBands = is('bands');
  // (a landmark whose style parameter is 0.99 or more is signs to its top: One Times Square)
  const signTop = sel(seed.greaterThan(0.985), height, min(mix(float(26), float(58), h1(seed.mul(3.3))), height.sub(2)));
  const onSigns = isSigns.and(isRoof.not()).and(positionWorld.y.sub(uv(2).x.mul(uvRange.base[0])).lessThan(signTop));
  const isCurtain = is('glass').or(isFins).or(isBands).or(isSigns.and(onSigns.not()));   // unitized glass walls
  const isLattice = where((d) => d.pattern === 'lattice'), isHoney = where((d) => d.pattern === 'honeycomb');
  const isPanel = where((d) => d.pattern === 'panel');
  // (portholes: built in only when a style uses it, Hong Kong's Jardine House; no other city's shader changes)
  const usePort = uses((d) => d.pattern === 'portholes'), isPort = usePort ? where((d) => d.pattern === 'portholes') : NONE;
  const isPattern = usePort ? isLattice.or(isHoney).or(isPanel).or(isPort) : isLattice.or(isHoney).or(isPanel);   // patterned skins, roofs included
  const curtainWall = f01(isCurtain.and(isRoof.not()));

  // ---- grid: a whole number of bays per wall run, a whole number of floors per building
  // (the style's bay width, m: styles.js `bay`)
  const bayDefault = pick(style, perStyle((d) => d.bay, 3.0))
    .mul(mix(float(0.85), float(1.2), h1(seed.mul(17.3))));
  // glass.variety: plain curtain walls (the glass style, no landmark module) get one of four rhythms, by the seed:
  // the standard grid, horizontal ribbons (tall spandrels, thin mullions, wider panes), full-height vertical glazing
  // (narrow panes, heavier mullions) and a low-spandrel grid on wide panes
  const rhythm = h1(seed.mul(53.3));
  const varied = variety ? is('glass').and(moduleM.lessThan(0.05)) : NONE;
  const rk = (a, b, c, d) => sel(rhythm.lessThan(0.3), float(a), sel(rhythm.lessThan(0.55), float(b), sel(rhythm.lessThan(0.8), float(c), float(d))));
  const bayNominal = sel(moduleM.greaterThan(0.05), moduleM, variety ? bayDefault.mul(sel(varied, rk(1, 1.5, 0.85, 2), float(1))) : bayDefault);
  const bays = max(float(1), round(runLen.div(bayNominal)));
  const X = s.div(runLen.div(bays));
  const floorNominal = pick(style, nominalFloor.map((f) => f || 3));
  const fh = wallH.div(max(float(1), round(wallH.div(floorNominal))));
  const F = y.div(fh);
  const cx = fract(X), col = floor(X);
  const cy = fract(F), row = floor(F);
  const wx = max(fwidth(X), 0.002).mul(0.75), wy = max(fwidth(F), 0.002).mul(0.75);

  // ---- window openings (fractions of a bay and of a floor)
  // shopfronts and lobbies (styles.js `shops`): "all" (apartment towers, villages, malls, cast-iron lofts, Times
  // Square), or a share of the buildings (Paris: most Haussmann blocks, many faubourg houses, some post-war and modern
  // blocks), by the city's shopSeed or (shopsBy "hash", New York's walk-ups) the building's own hash
  const shopShare = pick(style, perStyle((d) => (typeof d.shops === 'number' && d.shopsBy !== 'hash' ? d.shops : undefined), 0));
  // (city.json facade.shopSeed: 06_tiles put the buildings with a shopfront, the preset's shopfronts(), in the seed's
  // lower half: those of the styles with a shop share have one, no others)
  const shopDraw = shopSeed ? seed.lessThan(0.5).and(shopShare.greaterThan(0)) : h1(seed.mul(8.9)).lessThan(shopShare);
  const shopsByHash = users((d) => typeof d.shops === 'number' && d.shopsBy === 'hash')
    .reduce((acc, name) => acc.or(is(name).and(h1(seed.mul(8.9)).lessThan(styleData[name].shops))), where((d) => d.shops === 'all'));
  const shops = shopsByHash.or(shopDraw);
  const ground = row.lessThan(0.5).and(shops);
  // projecting balconies with a railing on a third of the columns (styles.js `balconies`)
  const balcony = where((d) => d.balconies)
    .and(h1(col.add(seed.mul(97.1))).lessThan(0.35)).and(ground.not());
  const finHalf = mix(float(0.03), float(0.15), seed).mul(sel(isPiers, float(2.6), float(1)));   // fins: seed = fin width; piers twice
  // the window box (styles.js `window` [xlo, ylo, yhi]; 0.5 for a style without windows)
  // (Haussmann's French windows reach down to the floor behind their rails)
  let xlo = sel(isFins, finHalf, pick(style, perStyle((d) => d.window?.[0], 0.5)));
  if (variety) xlo = sel(varied, rk(0.03, 0.015, 0.06, 0.03), xlo);
  let ylo = pick(style, perStyle((d) => d.window?.[1], 0.5));
  if (variety) ylo = sel(varied, rk(0.24, 0.38, 0.04, 0.14), ylo);
  let yhi = pick(style, perStyle((d) => d.window?.[2], 0.5));
  // the ground floor's shop windows (the preset's facade.shopfront: box [xlo, ylo, yhi]; doorEvery: a door down to the
  // pavement in every n-th bay. London: shopfronts between pilasters, over a stall riser, under a fascia; a door one bay
  // in three)
  const shopBox = shopfront.box ?? [0.06, 0.05, 0.84];
  const shopDoor = shopfront.doorEvery ? ground.and(col.add(floor(seed.mul(7))).mod(shopfront.doorEvery).equal(1)) : NONE;
  // (Berlin: Altbau balconies, a stucco slab and an iron railing in front of a French door, on the middle bay or the
  // two outer ones of a front (or none), from the first floor to the one under the top; the stripped fronts too)
  let altBalc = NONE;
  if (uses((d) => d.frenchBalconies)) {
    const bk = floor(h1(seed.mul(63.7)).mul(3));
    const topRow = round(wallH.div(fh)).sub(1);
    const balcCol = sel(bk.lessThan(0.5), f01(col.equal(floor(bays.mul(0.5)))),
      sel(bk.lessThan(1.5), f01(col.equal(1).or(col.equal(bays.sub(2)))), float(0)));
    altBalc = where((d) => d.frenchBalconies).and(balcCol.greaterThan(0.5)).and(bays.greaterThan(2.5)).and(row.greaterThan(0.5)).and(row.lessThan(topRow.sub(0.5)))
      .and(ground.not()).and(onWall);
    ylo = sel(altBalc, float(0.035), ylo);
  }
  // (Singapore: walls with no windows of their own, painted on the wall below (facade/patterns.js): an HDB slab's corridor
  // face above the ground floor (corridors: runs over 14 m whose normal leans towards a direction of the block's own, about
  // one long side), the void deck under a block over 20 m (voidDeck), a shophouse row's five-foot way (fiveFootWay))
  // (shophouseFront: the upper floors' windows its closed shutters cover)
  const sgOpen = uses((d) => d.corridors || d.voidDeck || d.fiveFootWay || d.shophouseFront);
  let corrWall = NONE, voidRow = NONE, arcadeRow = NONE, noOpen = NONE, shutRow = NONE, sgShut = NONE;
  if (sgOpen) {
    if (uses((d) => d.corridors)) {
      const a = h1(seed.mul(31.9)).mul(6.2832);
      corrWall = where((d) => d.corridors).and(runLen.greaterThan(14)).and(row.greaterThan(0.5))
        .and(normalWorldGeometry.x.mul(cos(a)).add(normalWorldGeometry.z.mul(sin(a))).greaterThan(0.3));
    }
    if (uses((d) => d.voidDeck)) voidRow = where((d) => d.voidDeck).and(row.lessThan(0.5)).and(height.greaterThan(20));
    if (uses((d) => d.fiveFootWay)) arcadeRow = where((d) => d.fiveFootWay).and(row.lessThan(0.5));
    if (uses((d) => d.shophouseFront)) {
      shutRow = where((d) => d.shophouseFront).and(row.greaterThan(0.5));
      sgShut = P.shophouseClosed({ col, row, seed });
    }
    noOpen = (uses((d) => d.shophouseFront) ? corrWall.or(voidRow).or(arcadeRow).or(shutRow.and(sgShut))
      : corrWall.or(voidRow).or(arcadeRow)).and(onWall).and(isRoof.not());
  }
  xlo = sel(ground, float(shopBox[0]), sel(balcony, float(0.1), xlo));
  const xhi = float(1).sub(xlo);
  ylo = sel(ground, shopfront.doorEvery ? sel(shopDoor, float(0.0), float(shopBox[1])) : float(shopBox[1]), sel(balcony, float(0.06), ylo));
  yhi = sel(ground, float(shopBox[2]), sel(balcony, float(0.9), yhi));

  const nearTop = smoothstep(wallH.sub(1.2), wallH.sub(0.7), y);                  // parapet band (or the eaves)
  // the cornice of masonry buildings under 60 m (styles.js cornice.maxHeight: limestone towers' to 100 m): a deep band
  // along the top (dark on brownstones and brick, a stone lip on the rest), which also keeps the top floor's windows
  // below it; its height times cornice.scale (palaces, London's terraces, Berlin's Altbau)
  const tallCornice = new Map();
  for (const name of users((d) => d.masonry && d.cornice?.maxHeight)) {
    const h = styleData[name].cornice.maxHeight;
    tallCornice.set(h, [...(tallCornice.get(h) ?? []), name]);
  }
  const hasCornice = f01([...tallCornice].reduce((acc, [h, names]) => acc.or(inStyles(names).and(height.lessThan(h))), isMasonry.and(height.lessThan(60))));
  const corniceH = mix(float(0.9), float(1.4), h1(seed.mul(37.1))).mul(byValue((d) => d.cornice?.scale, 1));
  const cornice = smoothstep(wallH.sub(corniceH).sub(fwidth(y)), wallH.sub(corniceH), y).mul(hasCornice).mul(f01(onWall));
  const open = band(cx, xlo, xhi, wx).mul(band(cy, ylo, yhi, wy))
    .mul(float(1).sub(nearTop)).mul(float(1).sub(cornice)).mul(sel(sgOpen ? isPlain.or(isRoof).or(isSpire).or(isFlood).or(isMon).or(onWall.not()).or(noOpen)
      : isPlain.or(isRoof).or(isSpire).or(isFlood).or(isMon).or(onWall.not()), float(0), float(1)));
  // balcony railings: a solid band across the lower third of the opening
  const rail = sel(balcony, band(cy, float(0.06), float(0.38), wy).mul(band(cx, xlo, xhi, wx)), float(0));
  // window frames: a thin border inside the opening, white or dark aluminium per building
  const inner = band(cx, xlo.add(0.035), xhi.sub(0.035), wx).mul(band(cy, ylo.add(0.045), yhi.sub(0.045), wy));
  const frameMask = open.sub(inner.mul(open)).max(0);
  const glassMask = open.sub(frameMask).mul(float(1).sub(rail)).max(0);
  // the share of dark frames and the light ones' colour (styles.js frames: London's painted sashes, white on nearly
  // every terrace, black iron on warehouses; Berlin's white casements on the Altbau, the courtyards, the post-war and
  // panel blocks)
  const frameT = byValue((d) => d.frames?.dark, 0.45);
  const frameLight = byValue((d) => d.frames?.light, [0.62, 0.62, 0.6], rgb);
  const frameColor = sel(h1(seed.mul(5.3)).greaterThan(frameT), frameLight, vec3(0.09, 0.09, 0.1));
  // air-conditioner units under some windows: everywhere in urban villages, fewer on apartment towers
  const acChance = pick(style, perStyle((d) => d.ac, 0));
  const acHere0 = h1(col.mul(7.13).add(row.mul(3.1)).add(seed.mul(11.7))).lessThan(acChance)
    .and(ground.not()).and(balcony.not());
  const acHere = sgOpen ? acHere0.and(noOpen.not()) : acHere0;
  const acX = mix(xlo, xhi.sub(0.32), h1(col.add(seed.mul(5.9))));
  const ac = sel(acHere, band(cx, acX, acX.add(0.3), wx).mul(band(cy, float(0.05), ylo.sub(0.04), wy)), float(0))
    .mul(float(1).sub(nearTop));

  // ---- pane variation that survives distance. Each pane gets random values (tilt, reflectance, blinds);
  // once panes shrink below a few pixels the values belong to groups of 2, 4, 8... bays (and floors, on
  // their own scale, since floors stay resolved much further than bays), blended between group sizes, so
  // the variation always sits on patches of at least ~2 pixels: a mottled, never shimmering surface.
  const fx = max(fwidth(X), 1e-4), fy = max(fwidth(F), 1e-4);
  const Lx = log2(max(fx.mul(4), 1)), Ly = log2(max(fy.mul(4), 1));
  const gx0 = exp2(floor(Lx)), gy0 = exp2(floor(Ly));
  const ax = fract(Lx), ay = fract(Ly);
  const cX0 = floor(col.div(gx0)), cX1 = floor(col.div(gx0.mul(2)));
  const cY0 = floor(row.div(gy0)), cY1 = floor(row.div(gy0.mul(2)));
  const seedInt = floor(seed.mul(4093));
  // group sizes differ per level, so the level goes into the hash too (else a 2-group and the 1-group at
  // its corner would share a value)
  const cellHash = (i, j, lx, ly) => hash(i.add(j.mul(613)).add(lx.mul(92821)).add(ly.mul(29537)).add(seedInt.mul(1543)));
  const lx0 = floor(Lx), ly0 = floor(Ly);
  const corners = [cellHash(cX0, cY0, lx0, ly0), cellHash(cX1, cY0, lx0.add(1), ly0),
    cellHash(cX0, cY1, lx0, ly0.add(1)), cellHash(cX1, cY1, lx0.add(1), ly0.add(1))];
  // value k of a group: four hashes serve every k (the hash's low bits, stretched by a different prime)
  const multi = (k) => {
    const v = corners.map((c) => (k ? fract(c.mul([0, 97, 389, 1409, 5807, 23201, 90001][k])) : c));
    return mix(mix(v[0], v[1], ax), mix(v[2], v[3], ax), ay);
  };
  // panes resolved (several pixels each): pillowing and blinds are drawn; smaller, they are averaged
  const paneNear = float(1).sub(smoothstep(float(0.2), float(0.5), max(fx, fy)));

  // ---- curtain walls: vision glass, spandrels, mullions, refuge floors, all box-filtered
  const visX = stripe(X, xlo, xhi, fx);                     // glass between the mullions (or fins)
  const visY = stripe(F, ylo, yhi, fy);                     // vision glass; below it the spandrel
  const mull = float(1).sub(visX);
  // what shows through vision glass: a dark office, darker or lighter per pane (lights, furniture,
  // depth), some panes with roller blinds pulled part way down (light grey), all through the glass tint
  const tint = wallColor;
  const interiorVar = multi(4);
  const blindShare = max(multi(5).sub(0.55), 0).mul(1.5);   // 0 (no blind) .. ~0.67 of the pane
  const blindNear = smoothstep(float(1).sub(blindShare).sub(fy.mul(0.5)), float(1).sub(blindShare).add(fy.mul(0.5)),
    cy.sub(ylo).div(max(yhi.sub(ylo), 0.01)));
  const blind = mix(blindShare.mul(0.9), blindNear, paneNear);
  const interior = mix(vec3(0.018, 0.02, 0.024), vec3(0.07, 0.068, 0.064), interiorVar)
    .mul(tint.mul(1.6).add(0.2));
  // the glass's own body colour (tinted float glass seen through its thickness) over the dark interior
  // silver: pale tints are reflective coated glass (One Vanderbilt, silver curtain walls), whose body reads
  // light grey in daylight however dark the interior behind it
  const silver = smoothstep(float(silverFrom), float(silverTo), dot(tint, vec3(0.2126, 0.7152, 0.0722)));
  // (silverDesat: the coated glass's body greyer than its tint, which the coating's reflection keeps)
  const silverBody = silverDesat > 0 ? mix(tint, vec3(dot(tint, vec3(0.2126, 0.7152, 0.0722))), silverDesat) : tint;
  const visionBody = mix(mix(interior.add(tint.mul(0.07)), vec3(0.2, 0.2, 0.195).mul(tint.add(0.5)), blind.mul(0.7)),
    silverBody.mul(0.55), silver.mul(0.8));
  // office ceiling lights: a faint line under the ceiling of about half the floors (box-filtered, so far
  // away it is a slight brightening of the vision glass), hidden where a blind is down
  const ceilingLights = stripe(F, yhi.sub(0.07), yhi.sub(0.035), fy).mul(f01(multi(6).greaterThan(0.5)))
    .mul(float(1).sub(blind)).mul(visX).mul(curtainWall);
  // spandrels: glass over an opaque back panel, dark or light grey per building; bands: light grey
  // (or darker glass) strips, per the seed
  let spandrelBody = sel(isBands, mix(tint.mul(0.6), vec3(0.47, 0.5, 0.53), seed),
    mix(tint.mul(0.3), vec3(0.24, 0.25, 0.26), f01(h1(seed.mul(9.1)).greaterThan(0.6))));
  // (glass.variety: on the varied towers spandrels of the glass's own tint over a light back panel, or metal)
  if (variety) spandrelBody = sel(varied, mix(tint.mul(0.62), vec3(0.3, 0.31, 0.32), f01(h1(seed.mul(9.1)).greaterThan(0.6))), spandrelBody);
  // mullions: aluminium; fins: brushed stainless, one side in shade so they read as projecting
  const stainless = vec3(0.66, 0.67, 0.69).mul(sel(cx.lessThan(0.5), float(0.78), float(1)));
  const terracotta = vec3(0.74, 0.64, 0.5).mul(sel(cx.lessThan(0.5), float(0.82), float(1)));
  const frame = sel(isPiers, mix(vec3(0.72, 0.62, 0.49), terracotta, paneNear), sel(isFins, mix(vec3(0.6, 0.61, 0.63), stainless, paneNear),
    mix(vec3(0.3, 0.31, 0.32), vec3(0.55, 0.56, 0.56), h1(seed.mul(3.1)))));
  // mechanical / refuge floors: on some towers over 150 m only, every 10 to 16 floors per tower, as a
  // louvred band of varying darkness; fins run through them. Box-filtered like the rest.
  const refugeEvery = floor(mix(float(10), float(16.99), h1(seed.mul(23.1))));
  const hasRefuge = f01(height.greaterThan(150).and(h1(seed.mul(41.7)).lessThan(refugeShare)).and(isFins.not()));
  const refugeRow = stripe(F.div(refugeEvery), float(1).sub(float(1).div(refugeEvery)), float(1), fy.div(refugeEvery))
    .mul(smoothstep(refugeEvery.mul(fh), refugeEvery.mul(fh).add(1), y));  // none at street level
  const refuge = refugeRow.mul(hasRefuge).mul(mix(float(0.35), float(0.8), h1(seed.mul(13.9)))).mul(curtainWall);
  const louvre = mix(vec3(0.12, 0.125, 0.13), vec3(0.2, 0.205, 0.21), stripe(F.mul(6), float(0), float(0.5), fy.mul(6)));
  // the crown: an aluminium coping line along the top edge of the glass
  const coping = smoothstep(height.sub(0.9).sub(fwidth(y)), height.sub(0.9), y);

  // ---- reflection geometry: each pane's normal tilted a little (panes are never quite coplanar) and
  // pillowed (bowed out towards its centre), spandrel panes set slightly differently from vision panes;
  // the amount varies per building, from crisp mirrors to wavy ones
  const N = normalize(normalWorldGeometry);
  const T = normalize(vec3(N.z, 0, N.x.negate()).add(vec3(1e-4, 0, 0)));     // along the wall, horizontal
  const B = vec3(0, 1, 0);
  const waviness = mix(float(0.002), float(0.008), h1(seed.mul(61.3)));
  // coarser groups tilt less (their panes' tilts partly average out)
  const groupFade = pow(float(0.6), Lx.add(Ly).mul(0.5));
  const pillow = paneNear.mul(0.01);
  const tiltX = multi(1).sub(0.5).mul(waviness).mul(groupFade).add(cx.sub(0.5).mul(pillow));
  const tiltY = multi(2).sub(0.5).mul(waviness).mul(groupFade)
    .add(cy.sub(mix(ylo, yhi, 0.5)).mul(pillow.mul(0.6))).add(float(1).sub(visY).mul(0.008));
  const tiltOn = f01(isPattern.not().and(isRoof.not()));
  const Np = normalize(N.add(T.mul(tiltX.mul(tiltOn))).add(B.mul(tiltY.mul(tiltOn))));
  const V = normalize(positionWorld.sub(cameraPosition));
  const ndv = max(dot(Np, V.negate()), 0);
  // (the reflection is built by a function: a second, fresh copy of its nodes goes into the emission's branch)
  const PROXY = 600;
  // live-tunable look (userData.tune on the material)
  const tune = { grazing: 0.5, skyDim: 0.65, skyDesat: 0.5, soft: 0.8, floor: 0, city: 0, reflectance: 1, coat: 0.35, ...glass };
  const glassTune = Object.fromEntries(Object.entries(tune).map(([k, v]) => [k, uniform(v)]));
  const probeAt = city ? city.center : uniform(new THREE.Vector3(0, CITY_PROBE_H, 0));
  // sub-pixel pane tilts blur what a pixel reflects: rougher lookups where panes are small
  const blurAmt = waviness.mul(4).add(0.05).mul(smoothstep(float(0.3), float(4), max(fx, fy)));
  let lookupRough = float(0.03).add(blurAmt).add(sel(isCurtain.or(isPattern), float(0), float(0.04)));
  const nearK = nearSoft ? float(1).sub(smoothstep(float(nearSoft[0]), float(nearSoft[1]), length(positionWorld.sub(cameraPosition)))) : null;
  if (nearSoft) lookupRough = lookupRough.add(nearK.mul(nearSoft[2]));
  const cityKnown = city ? city.captured : float(0);
  const reflectionOf = (Np, y, lookupRough) => {
    const N = normalize(normalWorldGeometry), V = normalize(positionWorld.sub(cameraPosition));
    let r = reflectDir(V, Np);
    r = normalize(r.add(N.mul(max(float(0.01).sub(dot(r, N)), 0))));            // never into the wall

    // what the glass reflects: the city probe, looked up parallax-corrected. The reflected world is taken
    // to be PROXY metres away along the reflected ray, or on the ground if the ray meets it first; the probe
    // is asked for that point. Far from the probe the proxy grows, to plain direction lookups, or a far
    // tower would only see itself from the probe.
    const fromProbe = positionWorld.sub(probeAt);
    const reach = float(PROXY).add(length(fromProbe).mul(4));
    const toGround = max(y, 0).div(max(r.y.negate(), 1e-4));
    const lookup = fromProbe.add(r.mul(min(reach, toGround)));
    // the haze between the glass and what it mirrors (the scene's fog is tuned for kilometres and all but
    // absent over a few hundred metres): a few percent of the sky's horizon colour, which keeps mirrored
    // streets from going black. Kept faint: more washes every tower into the same pale blue.
    const hazeColor = pmremTexture(env, vec3(r.x, 0.06, r.z), float(0.5)).rgb;
    const hazeAmount = float(1).sub(exp(min(min(reach, toGround), 1500).mul(-6e-5))).mul(smoothstep(float(0.25), float(0), r.y));
    // until the city is captured (or with ?reflect-city=0) only the sky map is there, whose lower half is a
    // bright void: below the horizon glass then shows a dim stand-in for the city, a third of the haze
    const raw = city ? city.sample(lookup, lookupRough).rgb : pmremTexture(env, r, lookupRough).rgb;
    const mirrored = mix(raw, hazeColor.mul(0.35), smoothstep(float(0.1), float(-0.05), r.y).mul(float(1).sub(cityKnown)));
    // the sky model is a clear, saturated blue; under a hazy sky (Shenzhen's usual one) what glass mirrors
    // above the horizon is paler and greyer, and less bright than the sky seen directly (it passes the coating twice)
    const skyPart = smoothstep(float(-0.1), float(0.03), r.y);          // the bright horizon counts as sky
    // city: what glass mirrors below the horizon is never darker than a sunlit street canyon's mean (warm grey,
    // this share of the horizon sky's brightness, so it fades at dusk): among skyscrapers the probe sees mostly
    // shaded walls and low views of glass went ink-black (Midtown)
    const cityLift = vec3(1, 0.95, 0.88).mul(dot(hazeColor, vec3(0.2126, 0.7152, 0.0722))).mul(glassTune.city);
    const mirroredLit = mix(max(mirrored, cityLift), mirrored, skyPart);
    const skyGrey = mix(mirrored, vec3(dot(mirrored, vec3(0.2126, 0.7152, 0.0722))), glassTune.skyDesat);
    // floor: a share of the sky's horizon colour in every reflection, for cities whose towers stand so close that
    // the probe sees mostly shaded walls and mirrored glass would go ink-black (Midtown)
    const reflectedLin = mix(mix(mix(mirroredLit, skyGrey.mul(glassTune.skyDim), skyPart), hazeColor, hazeAmount), hazeColor, glassTune.floor);
    // soft shoulder: the HDR horizon (brighter than 1) would otherwise turn grazing glass white
    return reflectedLin.div(reflectedLin.mul(glassTune.soft).add(1));
  };
  const reflected = reflectionOf(Np, y, lookupRough);

  // coated glass: 16-36 % reflectance head on (silvery towers more, clear ones less), rising to a mirror at
  // grazing angles; plain windows 5 %. Each pane (group) a little different. The coating tints the
  // reflection towards the glass colour (blue, green, silver).
  const f0Curtain = mix(float(0.16), float(0.36), h1(seed.mul(29.3))).mul(sel(isFins, float(0.8), float(1))).mul(glassTune.reflectance);
  const f0 = sel(isCurtain.or(isPattern), f0Curtain, float(windowF0)).mul(multi(3).sub(0.5).mul(0.2).mul(max(groupFade, 0.4)).add(1));
  // Schlick towards a capped grazing reflectance: tower glass never becomes a perfect mirror (coatings,
  // dirt, pane bow), so the body colour and the interior still read at oblique aerial angles
  const fresnel = f0.add(glassTune.grazing.sub(f0).max(0).mul(pow(float(1).sub(ndv), 5)));
  const tintLum = max(dot(tint, vec3(0.2126, 0.7152, 0.0722)), 0.02);
  const coat = mix(vec3(1, 1, 1), tint.div(tintLum), sel(isPattern, float(0.25), glassTune.coat));

  // curtain wall body (diffuse): glass passes 1 - F of what lies behind it
  const glassBody = mix(spandrelBody, visionBody, visY).mul(float(1).sub(fresnel));
  let glassWall = mix(glassBody, frame, mull);
  glassWall = mix(glassWall, louvre, refuge);
  glassWall = mix(glassWall, vec3(0.5, 0.51, 0.52), coping);
  // how much of a curtain wall reflects like glass: mullion caps a little, louvres hardly
  const curtainGlass = float(1).sub(mull.mul(0.8)).mul(float(1).sub(refuge.mul(0.75))).mul(float(1).sub(coping.mul(0.7)));

  // ---- patterned skins (landmarks); on roofs the pattern runs in map coordinates
  const U = sel(isRoof, positionWorld.x, s), Vc = sel(isRoof, positionWorld.z, y);
  const cellSize = sel(moduleM.greaterThan(0.05), moduleM, pick(style, perStyle((d) => d.cell, 1.2)));
  // lattice: two families of diagonal members; infill glass or white panels (seed = share of panels)
  const la = U.add(Vc).div(cellSize), lb = U.sub(Vc).div(cellSize);
  const latticeMember = max(lines(la, float(0.05)), lines(lb, float(0.05)));
  const latticeSolid = f01(hash2(floor(la), floor(lb)).lessThan(seed));
  // honeycomb: hexagonal cells (seed = share of glass cells)
  const hp = vec2(U, Vc).div(cellSize);
  const hr = vec2(1, 1.7320508);
  const ha = mod(hp, hr).sub(hr.mul(0.5));
  const hb = mod(hp.sub(hr.mul(0.5)), hr).sub(hr.mul(0.5));
  const hg = sel(dot(ha, ha).lessThan(dot(hb, hb)), ha, hb);
  const hid = hp.sub(hg);
  const hexEdge = max(abs(hg.x).mul(0.5).add(abs(hg.y).mul(0.8660254)), abs(hg.x));
  const honeyMember = uses((d) => d.pattern === 'honeycomb') ? smoothstep(float(0.44).sub(max(fwidth(hexEdge), 0.001)), float(0.46), hexEdge) : float(0);
  const honeyGlass = uses((d) => d.pattern === 'honeycomb') ? f01(hash2(hid.x, hid.y).lessThan(seed)) : float(0);
  // metal panels: seams every module and every 3 m, a glass strip every seventh panel
  const px = U.div(cellSize);
  const panelSeam = max(lines(px, float(0.02)), lines(Vc.div(3), float(0.012)));
  const panelGlass = f01(mod(floor(px), 7).equal(3).and(isRoof.not()));
  const white = vec3(0.8, 0.81, 0.8);
  let patternGlass = sel(isLattice, float(1).sub(latticeSolid), sel(isHoney, honeyGlass, panelGlass));
  let patternMember = sel(isLattice, latticeMember, sel(isHoney, honeyMember, panelSeam));
  const infill = mix(tint.mul(0.45).mul(sel(isHoney, vec3(0.5, 0.56, 0.62), vec3(1, 1, 1))),
    sel(isLattice, white.mul(0.95), tint.mul(mix(float(0.94), float(1.04), hash2(floor(px), floor(Vc.div(3)))))), patternGlass);
  const memberColor = sel(isPanel, tint.mul(0.7), white);
  let patternColor = mix(infill, memberColor, patternMember);
  // portholes (styles.js pattern 'portholes', opt-in): round windows (0.62 of the cell across) in a square grid of
  // cells on a light metal skin in the tint, a little darker round each window's rim; dark glass in them; roofs plain
  // metal (Jardine House, 1973: 1,748 round windows in white aluminium, one per bay and floor)
  if (usePort) {
    const pd = fract(vec2(U, Vc).div(cellSize)).sub(0.5), pr = length(pd), pfw = max(fwidth(pr), 0.002);
    const port = float(1).sub(smoothstep(float(0.31).sub(pfw), float(0.31), pr)).mul(f01(isRoof.not()));
    const portRim = smoothstep(float(0.28), float(0.31), pr).mul(float(1).sub(smoothstep(float(0.33), float(0.37), pr))).mul(f01(isRoof.not()));
    patternGlass = sel(isPort, port, patternGlass);
    patternMember = sel(isPort, float(1).sub(port), patternMember);
    patternColor = sel(isPort, mix(vec3(0.05, 0.06, 0.07), tint.mul(float(1).sub(portRim.mul(0.25))), float(1).sub(port)), patternColor);
  }

  // ---- walls: weathering streaks under windows, grime near the ground, a little per-bay variation
  const streak = sel(isCurtain, float(0), band(cx, xlo, xhi, wx).mul(float(1).sub(smoothstep(float(0), ylo, cy)))
    .mul(h1(col.add(seed.mul(31.7))).mul(0.1)));
  const grime = sel(isVillage.or(isFactory), float(1).sub(smoothstep(float(0), float(3), y)).mul(0.22), float(0));
  const panelVar = h1(col.mul(3.7).add(floor(F.div(4)).mul(5.3)).add(seed)).sub(0.5).mul(0.06);
  // masonry close up: bricks and stones mottled a little (courses of 0.4 x 0.15 m, averaged away with distance)
  const courseRes = float(1).sub(smoothstep(float(0.3), float(1.2), max(fwidth(s).div(0.4), fwidth(y).div(0.15))));
  const mottle = hash2(floor(s.div(0.4).add(floor(y.div(0.15)).mul(0.5))), floor(y.div(0.15))).sub(0.5)
    .mul(byValue((d) => ({ brick: 0.12, stone: 0.05 })[d.mottle], 0).mul(courseRes));
  let wall = wallColor.mul(float(1).sub(streak).sub(grime).add(panelVar).add(mottle));
  // a stone base: the lowest floor or two of limestone and brick buildings in a lighter or darker stone
  const baseH = fh.mul(sel(h1(seed.mul(19.9)).lessThan(0.5), float(1), float(2)));
  const stoneBase = f01(where((d) => d.stoneBase)).mul(float(1).sub(smoothstep(baseH.sub(0.1), baseH, y)))
    .mul(f01(h1(seed.mul(12.7)).lessThan(0.55)));
  wall = mix(wall, sel(h1(seed.mul(4.4)).lessThan(0.6), vec3(0.55, 0.52, 0.46), vec3(0.22, 0.21, 0.2)), stoneBase.mul(0.8));
  const fyM = max(fwidth(y), 1e-3);
  // ---- balcony rows (styles.js balconyRows: continuous iron balconies on these floors, on a share of the buildings by
  // the seed's hash; shadow: their shadow on the floor below): Haussmann's on the 2nd and 5th floors, London's terraces'
  // first floor on some
  const rowsAt = (rows) => rows.map((r) => row.equal(r)).reduce((a, b) => a.or(b));
  const balcGroups = new Map();
  for (const name of users((d) => d.balconyRows)) {
    const b = styleData[name].balconyRows, k = JSON.stringify(b.rows);
    if (!balcGroups.has(k)) balcGroups.set(k, { rows: b.rows, plain: [], shared: [] });
    balcGroups.get(k)[b.share ? 'shared' : 'plain'].push(name);
  }
  let balcRow = NONE;
  for (const g of balcGroups.values()) {
    const terms = [];
    if (g.plain.length) terms.push(inStyles(g.plain).and(rowsAt(g.rows)));
    if (g.shared.length) terms.push(rowsAt(g.rows).and(g.shared.map((n) => shareOf(is(n), seed, styleData[n].balconyRows)).reduce((a, b) => a.or(b))));
    for (const t of terms) {
      const t2 = t.and(onWall).and(isRoof.not()).and(slopeRoof.not());
      balcRow = balcRow === NONE ? t2 : balcRow.or(t2);
    }
  }
  const shadowUsers = users((d) => d.balconyRows?.shadow);
  const balcShadow = shadowUsers.length ? f01(inStyles(shadowUsers).and(rowsAt(styleData[shadowUsers[0]].balconyRows.rows.map((r) => r - 1))).and(onWall))
    .mul(band(cy, float(0.9), float(1.02), wy)) : null;
  // ---- the wall's own features (styles without a wall-detail branch: Paris's). Rustication (styles.js rustication:
  // grooves every `groove` m on the lowest `rows` floors, not behind shops, darkened by depth): Haussmann's ground floor
  // and entresol; brick and stone: stone bands at each floor (floorBands: stone, or concrete on HBM), window surrounds
  // and quoins; precast panels: dark spandrels between the piers on some towers
  const topRustic = users((d) => onTop(d) && d.rustication);
  const rusticate = topRustic.length ? f01(rusticTest(topRustic, { row, notGround: ground.not(), isOf: is }))
    .mul(rusticJoints({ y, fyM }, styleData[topRustic[0]].rustication)) : null;
  if (rusticate && balcShadow) wall = wall.mul(float(1).sub(rusticate.mul(styleData[topRustic[0]].rustication.depth)).sub(balcShadow.mul(styleData[shadowUsers[0]].balconyRows.shadow)));
  else if (rusticate) wall = wall.mul(float(1).sub(rusticate.mul(styleData[topRustic[0]].rustication.depth)));
  else if (balcShadow) wall = wall.mul(float(1).sub(balcShadow.mul(styleData[shadowUsers[0]].balconyRows.shadow)));
  if (uses((d) => d.floorBands || d.surrounds || d.quoins)) {
    const floorBand = f01(where((d) => d.floorBands).and(onWall)).mul(band(cy, float(0.88), float(1.0), wy));
    const surround = f01(where((d) => d.surrounds).and(onWall).and(ground.not())).mul(band(cx, xlo.sub(0.08), xhi.add(0.08), wx))
      .mul(band(cy, ylo.sub(0.06), yhi.add(0.06), wy));
    const quoin = f01(where((d) => d.quoins).and(onWall).and(s.lessThan(1.1).or(s.greaterThan(runLen.sub(1.1)))))
      .mul(stripe(y.div(0.7), float(0), float(0.55), fyM.div(0.7)));
    wall = mix(wall, byValue((d) => ({ concrete: [0.6, 0.56, 0.49] })[d.floorBands], [0.69, 0.62, 0.49], rgb), clamp(floorBand.add(surround).add(quoin), 0, 1).mul(0.9));
  }
  if (uses((d) => d.panelSpandrels)) {
    const panelSpandrel = f01(where((d) => d.panelSpandrels).and(ground.not()).and(onWall)).mul(band(cx, xlo, xhi, wx))
      .mul(float(1).sub(band(cy, ylo, yhi, wy)));
    wall = mix(wall, sel(h1(seed.mul(27.7)).lessThan(0.55), vec3(0.075, 0.055, 0.065), wallColor.mul(0.62)), panelSpandrel.mul(0.9));
  }
  // ---- the tropical blocks' and rows' patterns (facade/patterns.js; Singapore's styles), on the wall itself: they read
  // from the air (box-filtered, each averages out far away). HDB's accent paint (paintBands), corridor faces (corridors),
  // void decks (voidDeck), the five-foot way (fiveFootWay), a colonial colonnade (colonnade), condo slab edges
  // (balconySlabs), a shophouse's shutters and pilasters (shophouseFront)
  if (uses((d) => d.paintBands || d.corridors || d.voidDeck || d.fiveFootWay || d.colonnade || d.balconySlabs || d.shophouseFront)) {
    const onW = onWall.and(isRoof.not()).and(slopeRoof.not());
    const c = { seed, y, F, X, cx, cy, fx, fy, wy, fyM, fs: max(fwidth(s), 1e-3), s, runLen, wallH, fh, row };
    const top = round(wallH.div(fh)).sub(1);
    // (facade.patternBranch, Singapore M9: each pattern in an If on its own mask, from copies of its inputs, so a wall pays
    // only for its own style's patterns and glass, roofs and the other styles for none; each pattern is mix(wall, its
    // colour, mask), the wall itself where the mask is 0, so the picture is the same)
    if (patternBranch) {
      const on = {};
      if (uses((d) => d.paintBands)) on.paintBands = where((d) => d.paintBands).and(onW);
      if (uses((d) => d.balconySlabs)) on.balconySlabs = where((d) => d.balconySlabs).and(onW);
      if (uses((d) => d.colonnade)) on.colonnade = where((d) => d.colonnade).and(onW).and(row.lessThan(top.add(0.5)));
      if (uses((d) => d.corridors)) on.corridors = corrWall.and(onW);
      if (uses((d) => d.voidDeck)) on.voidDeck = voidRow.and(onW);
      if (uses((d) => d.fiveFootWay)) on.fiveFootWay = arcadeRow.and(onW);
      if (uses((d) => d.shophouseFront)) { on.shophouseFront = shutRow.and(onW); on.closed = sgShut; }
      const patIn = { ...c, wall, col, xlo, xhi, ylo, yhi, cut: float(1).sub(nearTop).mul(float(1).sub(cornice)),
        ...Object.fromEntries(Object.entries(on).map(([k, m]) => [`on_${k}`, f01(m)])) };
      wall = Fn(() => {
        const V = Object.fromEntries(Object.entries(patIn).map(([k, n]) => [k, n.toVar()]));
        const w = V.wall.toVar();
        const yes = (k) => V[`on_${k}`].greaterThan(0.5);
        const run = (k, f) => { if (on[k]) If(yes(k), () => { w.assign(f({ ...V, wall: w }, yes(k))); }); };
        run('paintBands', P.paintBands);
        run('balconySlabs', P.balconySlabs);
        run('colonnade', P.colonnade);
        run('corridors', P.corridorAccess);
        run('voidDeck', P.voidDeck);
        run('fiveFootWay', P.fiveFootWay);
        run('shophouseFront', (V2, m) => P.shophouseFront(V2, m, yes('closed')));
        return w;
      })();
    } else {
    if (uses((d) => d.paintBands)) wall = P.paintBands({ ...c, wall }, where((d) => d.paintBands).and(onW));
    if (uses((d) => d.balconySlabs)) wall = P.balconySlabs({ ...c, wall }, where((d) => d.balconySlabs).and(onW));
    if (uses((d) => d.colonnade)) wall = P.colonnade({ ...c, wall }, where((d) => d.colonnade).and(onW).and(row.lessThan(top.add(0.5))));
    if (uses((d) => d.corridors)) wall = P.corridorAccess({ ...c, wall }, corrWall.and(onW));
    if (uses((d) => d.voidDeck)) wall = P.voidDeck({ ...c, wall }, voidRow.and(onW));
    if (uses((d) => d.fiveFootWay)) wall = P.fiveFootWay({ ...c, wall }, arcadeRow.and(onW));
    if (uses((d) => d.shophouseFront)) {
      wall = P.shophouseFront({ ...c, wall, col, xlo, xhi, ylo, yhi, cut: float(1).sub(nearTop).mul(float(1).sub(cornice)) },
        shutRow.and(onW), sgShut);
    }
    }
  }
  // ---- the wall-detail branch without fade ('none': London's terraces, mansion blocks, Portland stone, estates,
  // warehouses and modern blocks). In a branch only those walls pay for (roofs, glass and other styles skip it), built
  // from copies of its inputs and without derivatives (the widths wx, wy, fyM are taken before), as nearOut below.
  // (London M4, Ludgate Hill street view, same tiles, settled frame: 177 ms for the shader without London's styles, 196
  // with this block inline, 191 in the branch.) Its layers in this order: a painted stucco ground floor (stuccoGround:
  // on a share, paint: recoloured), rustication, polychrome bands (a red band over each row of windows, a pale one at
  // the sills), stone sill and lintel bands and a stone ground floor (stoneBands, stoneGround), deck-access balcony
  // fronts or concrete floor bands (decks), brick courses, loading doors with their iron platforms (loadingDoors),
  // shopfronts (the preset's facade.shopfront), a string course over the ground floor (stringCourse: stone, or the
  // wall's own a shade lighter), a pillared porch one bay in three (porch), the cornice's shadow (corniceShadow)
  let wareDoor = float(0);
  if (anyNone) {
    const N = users(fadeNone), inN = (test) => (d) => fadeNone(d) && test(d), usesN = (test) => uses(inN(test));
    const lonOn = where(fadeNone).and(onWall).and(isRoof.not()).and(slopeRoof.not());
    // (its inputs taken now: the Fn is built later, when `wall` is already lonOut itself: a node loop)
    const fsM = max(fwidth(s), 1e-3);
    const mortarRes = brickRes(fyM, fsM);
    const lonIn = { wall, seed, row, col, cx, cy, ylo, yhi, wx, wy, y, fyM, bays, cornice, style, ground: f01(ground),
      s, fsM, mortarRes, wallH, corniceH };
    const lonOut = Fn(() => {
      const V = Object.fromEntries(Object.entries(lonIn).map(([k, n]) => [k, n.toVar()]));
      const out = vec4(V.wall, 0).toVar();
      If(lonOn, () => {
        const isV = (name) => (ID[name] === undefined ? NONE : V.style.equal(ID[name]));
        const whereV = (test) => where(inN(test), isV);
        // a feature's users, each on its share of buildings (shareOf: styles.js { share, hash })
        const shareV = (get) => users(inN(get)).map((name) => shareOf(isV(name), V.seed, get(styleData[name]))).reduce((a, b) => (a ? a.or(b) : b), null) ?? NONE;
        const notGround = V.ground.lessThan(0.5);
        let w = V.wall, door = float(0), porch = float(0);
        const on = {};
        if (usesN((d) => d.stuccoGround)) {
          on.stuccoGround = shareV((d) => d.stuccoGround).and(V.row.lessThan(0.5));
          const stuccoC = vec3(0.72, 0.69, 0.62).mul(mix(float(0.92), float(1.04), h1(V.seed.mul(8.3))));
          w = mix(w, stuccoC, f01(on.stuccoGround.and(whereV((d) => d.stuccoGround?.paint))));
        }
        const rN = users(inN((d) => d.rustication));
        if (rN.length) {
          const r = styleData[rN[0]].rustication;
          const rustic = f01(rusticTest(rN, { row: V.row, notGround, isOf: isV, on })).mul(rusticJoints(V, r));
          w = w.mul(float(1).sub(rustic.mul(r.depth)));
        }
        if (usesN((d) => d.polychrome)) {
          const poly = f01(shareV((d) => d.polychrome).and(notGround));
          const redBand = bandAt(V, 'lintel', 0.025, 0.085).mul(poly);
          const sillBand = bandAt(V, 'sill', -0.045, 0).mul(poly);
          w = mix(mix(w, vec3(0.25, 0.08, 0.05), redBand.mul(0.85)), vec3(0.6, 0.55, 0.45), sillBand.mul(0.8));
        }
        if (usesN((d) => d.stoneBands || d.stoneGround)) {
          const mBands = f01(whereV((d) => d.stoneBands)).mul(clamp(bandAt(V, 'sill', -0.07, 0).add(bandAt(V, 'lintel', 0, 0.06)), 0, 1));
          const mBase = f01(shareV((d) => d.stoneGround).and(V.row.lessThan(0.5)));
          w = mix(w, vec3(0.6, 0.53, 0.42), clamp(mBands.mul(0.85).add(mBase.mul(0.9)), 0, 1));
        }
        if (usesN((d) => d.decks)) {
          const deck = shareV((d) => d.decks).and(V.row.greaterThan(0.5));
          const deckM = f01(deck).mul(band(V.cy, float(0), V.ylo.sub(0.02), V.wy));
          const eBand = f01(whereV((d) => d.decks).and(deck.not())).mul(band(V.cy, float(0.9), float(1.0), V.wy));
          w = mix(w, vec3(0.5, 0.48, 0.44).mul(mix(float(0.85), float(1.1), h1(V.seed.mul(4.1)))), clamp(deckM.add(eBand), 0, 1).mul(0.92));
        }
        const bN = users(inN((d) => d.brickCourses));
        if (bN.length) w = brickCourses(w, { y: V.y, s: V.s, fyM: V.fyM, fs: V.fsM, res: V.mortarRes }, styleData[bN[0]].brickCourses, f01(inStyles(bN, isV)));
        if (usesN((d) => d.loadingDoors)) {
          const doorCol = shareV((d) => d.loadingDoors).and(V.bays.greaterThan(2.5))
            .and(V.col.add(floor(V.seed.mul(5))).mod(3).equal(1)).and(notGround);
          ({ w, door } = P.loadingDoors(V, w, doorCol));
        }
        const shopG = V.ground.greaterThan(0.5);
        if (usesN((d) => d.shopfront)) {
          const all = N.every((n) => styleData[n].shopfront);
          w = shopfrontOf(w, V, SF, { gate: f01(all ? shopG : shopG.and(whereV((d) => d.shopfront))),
            pilasterK: SF.tint ? byValue((d) => (fadeNone(d) ? d.shopfront?.pilasters : undefined), SF.tint.pilasters, float, isV) : null });
        }
        if (usesN((d) => d.stringCourse)) {
          const string = f01(whereV((d) => d.stringCourse).and(V.row.lessThan(0.5)).and(shopG.not())).mul(band(V.cy, float(0.93), float(1.0), V.wy));
          w = mix(w, sel(whereV((d) => d.stringCourse === 'self'), V.wall.mul(1.07), vec3(0.6, 0.57, 0.5)), string.mul(0.9));
        }
        if (usesN((d) => d.porch)) {
          const p = P.pillaredPorch(V, whereV((d) => d.porch).and(V.row.lessThan(0.5)).and(shopG.not()).and(V.col.add(floor(V.seed.mul(3))).mod(3).equal(0)));
          porch = p.mask;
          w = mix(w, p.colour, porch);
        }
        const cN = users(inN((d) => d.corniceShadow));
        if (cN.length) {
          const cs = styleData[cN[0]].corniceShadow;
          w = w.mul(float(1).sub(corniceShadow(V, cs.depth).mul(cs.k).mul(f01(inStyles(cN, isV)))));
        }
        out.assign(vec4(w, max(door, porch)));
      });
      return out;
    })();
    wall = lonOut.xyz;
    wareDoor = lonOut.w;
  }
  // ---- the wall-detail branch that fades with the bays ('bays': Berlin's fronts), its features in this order:
  // Gründerzeit stucco (gruenderzeit; stucco: the fronts that kept theirs, all but the share `stripped` after the war):
  // string courses at every floor with their shadow (stringCourses: without the stucco too), the cornice's shadow and
  // its profile (consoles, dentils, corona; a plain eave on stripped fronts), window surrounds, hoods and a pediment
  // over the Beletage, sills, the French balconies' slabs (frenchBalconies), rustication, pilasters every n bays,
  // a frieze under the cornice, ceramic tiles (ceramicTiles: Karl-Marx-Allee); then Plattenbau (panel joints, loggia
  // columns with coloured fronts, a darker plinth), slab edges and coloured balcony panels (slabEdges: Hansaviertel),
  // stone joints and a recessed top floor (stoneJoints: Neubau), precast joints and light spandrels (precast), brick
  // courses, stone or yellow-brick sill and lintel bands (sillBands), buttresses; shopfronts (facade.shopfront: boards
  // with letters, pilasters, riser). In a branch only these walls pay for, built from copies of its inputs and without
  // derivatives (as the 'none' branch)
  let berCornice = float(0);
  if (anyBays) {
    // (only where the window grid is resolved: farther, the walls are their average anyway and the overview's walls,
    // nearly all of them past the fade, skip the branch; the detail fades out with the same smoothstep as the grid.
    // Berlin M4 overview, settled: 212 ms with the branch on every Berlin wall)
    // (M4 fix round: the horizontal profiles, the cornice and the string courses, fade with the floors' size on screen
    // alone (farH), not the bays': along a street the fronts are seen at a grazing angle, their bays a pixel wide and
    // their floors tens of pixels high, and the receding cornice lines are what reads there)
    // (facade.bayFade [from, to], Hong Kong's and Tokyo's M4 fix rounds: the branch's own fade, closer than the grid's, so that the
    // walls' detail in the middle distance of a street view is paid for only where it reads)
    const farB = bayFade ? smoothstep(float(bayFade[0]), float(bayFade[1]), max(wx, wy)) : smoothstep(float(0.12), float(0.35), max(wx, wy));
    // (the profiles only where a floor is 10 px or more: their bands need it, and farther they were a cost on every
    // Berlin wall in the overview's foreground for nothing to see: 205 ms settled against 186 without)
    const farH = smoothstep(float(0.05), float(0.1), wy);
    const berOn = where(fadeBays).and(onWall).and(isRoof.not()).and(slopeRoof.not())
      .and(farB.lessThan(0.999).or(farH.lessThan(0.999)));
    const fsB = max(fwidth(s), 1e-3);
    const fineRes = brickRes(fyM, fsB);
    const tileRes = float(1).sub(smoothstep(float(0.15), float(0.5), max(fyM.div(0.24), fsB.div(0.32))));
    const berIn = { wall, seed, row, col, cx, cy, xlo, xhi, ylo, yhi, wx, wy, y, fyM, fsB, fineRes, tileRes, bays, cornice, style,
      ground: f01(ground), s, wallH, corniceH, fh, farB, altBalc: f01(altBalc) };
    const berOut = Fn(() => {
      const V = Object.fromEntries(Object.entries(berIn).map(([k, n]) => [k, n.toVar()]));
      const out = vec4(V.wall, 0).toVar();
      If(berOn, () => {
        // (each style's detail in a branch of its own: a wall pays for its style's patterns only; every node a branch
        // uses is built inside it, its result written to w. Berlin M4 street view: 225 ms settled with all of them
        // computed for every Berlin wall)
        const isV = (name) => (ID[name] === undefined ? NONE : V.style.equal(ID[name]));
        const whereV = (test) => where((d) => fadeBays(d) && test(d), isV), usesB = (test) => uses((d) => fadeBays(d) && test(d));
        // (fresh nodes per use: a node first built inside one branch would be declared in its scope only)
        const shopG = () => V.ground.greaterThan(0.5), notG = () => V.ground.lessThan(0.5);
        const w = V.wall.toVar();
        // the horizontal profiles (colour, weight), faded by farH: the cornice (hzC weight 1 where drawn: the shared
        // cornice band is then left out) and the string courses
        const hzC = V.wall.toVar(), hzW = float(0).toVar(), hzCor = float(0).toVar();
        const lightOf = (c) => c.mul(1.12).add(0.025).min(vec3(0.92));
        // Altbau, sandstone, Karl-Marx-Allee: the horizontal profiles everywhere the floors are resolved (a grazing view
        // along a street), the bays' detail where they are
        if (usesB((d) => d.gruenderzeit)) If(whereV((d) => d.gruenderzeit), () => {
          const light = lightOf(V.wall);
          const stucco = users((d) => fadeBays(d) && d.stucco).map((name) => shareOf(isV(name), V.seed, styleData[name].stucco))
            .reduce((x, y) => (x ? x.or(y) : y), null) ?? NONE;
          const courses = stucco.or(whereV((d) => d.stringCourses));
          // horizontal: a string course at every floor (a lit top, the projection's shadow under it), a broader one
          // over the ground floor; the cornice's shadow on the wall under it; the cornice itself, profiled (bottom to
          // top: a frieze with consoles every 0.9 m, the soffit's shadow, a dentil course, the corona, a shadow line, a
          // lit top moulding); a stripped front keeps a plain eave with its soffit shadow
          If(V.wy.lessThan(0.1), () => {
            const g = P.gruenderzeitProfile(V, courses, light);
            hzC.assign(g.colour);
            hzW.assign(g.weight);
            hzCor.assign(g.cornice);
          });
          If(V.farB.lessThan(0.999), () => {
            let c = P.gruenderzeitSurrounds(V, stucco, notG, light);
            if (usesB((d) => d.frenchBalconies)) c = P.frenchBalcony(V, c);
            const rB = users((d) => fadeBays(d) && d.rustication);
            if (rB.length) {
              const rust = f01(rusticTest(rB, { row: V.row, notGround: notG(), isOf: isV, on: { stucco } })).mul(rusticJoints(V, styleData[rB[0]].rustication));
              c = c.mul(float(1).sub(rust.mul(styleData[rB[0]].rustication.depth)));
            }
            if (usesB((d) => d.pilasters)) {
              c = P.pilasterStrips(V, c, users((d) => fadeBays(d) && d.pilasters)
                .map((name) => isV(name).and(V.col.mod(styleData[name].pilasters.every).equal(0))).reduce((a, b) => a.or(b)), light);
            }
            if (usesB((d) => d.frieze)) c = P.frieze(V, c, whereV((d) => d.frieze), light);
            if (usesB((d) => d.ceramicTiles)) c = P.ceramicTiles(V, c, whereV((d) => d.ceramicTiles).and(notG()));
            w.assign(c);
          });
        });
        // the other styles' detail and the shopfronts, where the bays are resolved
        If(V.farB.lessThan(0.999), () => {
          // the pattern library's slabs and panels (facade/patterns.js)
          if (usesB((d) => d.plattenbau)) If(whereV((d) => d.plattenbau), () => { w.assign(P.plattenbau(V)); });
          if (usesB((d) => d.slabEdges)) If(whereV((d) => d.slabEdges), () => { w.assign(P.slabEdges(V)); });
          if (usesB((d) => d.stoneJoints)) If(whereV((d) => d.stoneJoints).and(notG()), () => { w.assign(P.stoneJoints(V)); });
          if (usesB((d) => d.precast)) If(whereV((d) => d.precast).and(notG()), () => { w.assign(P.precastJoints(V, lightOf)); });
          // Japan's walls (facade/patterns.js): tiled bands, apartment balcony railings, temples' timber frames, low
          // wooden houses' siding
          if (usesB((d) => d.tileBands)) If(whereV((d) => d.tileBands).and(notG()), () => { w.assign(P.tiledBands(V)); });
          if (usesB((d) => d.balconyRails)) If(whereV((d) => d.balconyRails), () => { w.assign(P.balconyRails(V)); });
          if (usesB((d) => d.timberFrame)) If(whereV((d) => d.timberFrame), () => { w.assign(P.timberFrame(V)); });
          if (usesB((d) => d.lapSiding)) If(whereV((d) => d.lapSiding), () => { w.assign(P.lapSiding(V)); });
          // high-rise housing, shophouses and flatted factories (Hong Kong M4): public housing's colour accents, tiled
          // towers' bay windows, shophouse balconies and first-floor signboards, factories' spandrels and shutters,
          // colonial verandahs
          if (usesB((d) => d.estateAccents)) If(whereV((d) => d.estateAccents), () => { w.assign(P.estateAccents(V)); });
          if (usesB((d) => d.bayWindows)) If(whereV((d) => d.bayWindows), () => { w.assign(P.bayWindows(V)); });
          if (usesB((d) => d.shophouseBalconies)) If(whereV((d) => d.shophouseBalconies), () => { w.assign(P.shophouseBalconies(V, notG).colour); });
          if (usesB((d) => d.ribbonSpandrels)) If(whereV((d) => d.ribbonSpandrels), () => { w.assign(P.ribbonSpandrels(V, notG).colour); });
          if (usesB((d) => d.verandahArcade)) If(whereV((d) => d.verandahArcade), () => { w.assign(P.verandahArcade(V).colour); });
          if (usesB((d) => d.tiledWall)) If(whereV((d) => d.tiledWall), () => { w.assign(P.tiledWall(V)); });
          // brick (klinker, churches)          // brick (klinker, churches): mortar courses close up, a stone or yellow-brick band at the sills and over the
          // windows; churches' buttresses at each bay's edge
          if (usesB((d) => d.brickCourses)) If(whereV((d) => d.brickCourses), () => {
            let c = brickCourses(V.wall, { y: V.y, s: V.s, fyM: V.fyM, fs: V.fsB, res: V.fineRes },
              styleData[users((d) => fadeBays(d) && d.brickCourses)[0]].brickCourses);
            const kBand = f01(whereV((d) => d.sillBands).and(notG())).mul(bandAt(V, 'sill', -0.05, 0).add(bandAt(V, 'lintel', 0, 0.07)).min(1));
            c = mix(c, sel(h1(V.seed.mul(3.9)).lessThan(0.5), vec3(0.55, 0.47, 0.33), vec3(0.62, 0.58, 0.5)), kBand.mul(0.8));
            w.assign(usesB((d) => d.buttresses) ? P.buttresses(V, c, whereV((d) => d.buttresses)) : c);
          });
          // shopfronts (the preset's facade.shopfront; Berlin M4 fix round: the boards were near-black, the shopfronts read
          // as black bands)
          if (uses((d) => fadeBays(d) && d.shopfront)) {
            If(shopG(), () => { w.assign(shopfrontOf(w, { ...V, fs: V.fsB }, SF, { light: lightOf })); });
          }
        });
        const near = mix(w, V.wall, V.farB);
        const nearH = float(1).sub(smoothstep(float(0.05), float(0.1), V.wy));
        out.assign(vec4(mix(near, hzC, hzW.mul(nearH)), hzCor.mul(nearH)));
      });
      return out;
    })();
    wall = berOut.xyz;
    berCornice = berOut.w;
  }

  // limestone towers of the 1920s-30s: windows in continuous vertical strips between piers, the spandrels
  // between them recessed and dark
  const strips = f01(where((d) => d.windowStrips).and(h1(seed.mul(27.7)).lessThan(0.6)).and(ground.not()));
  const spandrel = band(cx, xlo, xhi, wx).mul(float(1).sub(band(cy, ylo, yhi, wy))).mul(strips).mul(float(1).sub(cornice));
  wall = mix(wall, wallColor.mul(0.35), spandrel.mul(0.85));
  // fire escapes on the street fronts of walk-ups: iron platforms at each floor across two bays in the
  // middle of a run and a railing, from the second floor up (box-filtered: a dark grille far away)
  const midCol = floor(bays.mul(0.5)).sub(1);
  const escape = f01(where((d) => d.fireEscape).and(h1(seed.mul(15.3)).lessThan(0.45)).and(runLen.greaterThan(6)).and(runLen.lessThan(40))
    .and(row.greaterThan(0.5)).and(col.greaterThan(midCol.sub(0.5))).and(col.lessThan(midCol.add(1.5))))
    .mul(float(1).sub(cornice));
  const platform = stripe(F, float(0), float(0.05), fy);
  const railing = stripe(F, float(0.05), float(0.36), fy).mul(stripe(X.mul(8), float(0), float(0.25), fx.mul(8)).mul(0.8).add(0.1));
  const ladder = stripe(F.add(X.mul(0.5)), float(0.46), float(0.52), max(fy, fx.mul(0.5))).mul(0.7);
  const ironwork0 = uses((d) => d.fireEscape) ? clamp(platform.add(railing).add(ladder), 0, 1).mul(escape) : float(0);
  // Haussmann's wrought iron: continuous balconies along the 2nd and 5th floors (a rail a third of the storey high,
  // its balusters box-filtered into a grey tone far away), guard rails across the French windows of the others
  const balusters = stripe(X.mul(14), float(0), float(0.45), fx.mul(14)).mul(0.55).add(0.35);
  const balc = f01(balcRow).mul(band(cy, float(0.0), float(0.3), wy)).mul(balusters);
  const guard = f01(isGuarded.and(balcRow.not()).and(row.greaterThan(1.5)).and(onWall))
    .mul(band(cy, ylo, ylo.add(0.2), wy)).mul(band(cx, xlo, xhi, wx)).mul(balusters);
  const hasBalc = uses((d) => d.balconyRows), hasGuard = uses((d) => d.guardRails), hasShutters = uses((d) => d.shutters);
  const ironwork = hasBalc && hasGuard ? max(ironwork0, max(balc, guard)) : hasBalc ? max(ironwork0, balc) : hasGuard ? max(ironwork0, guard) : ironwork0;
  // the cornice's colour (styles.js cornice.colour): light (a stone lip), mix (London: stone over brick), or dark
  const lightCornice = where((d) => d.cornice?.colour === 'light'), mixCornice = where((d) => d.cornice?.colour === 'mix');
  // (London: stone copings and cornices over brick and stucco; the warehouses' brick parapet stays dark)
  const corniceColor = uses((d) => d.cornice?.colour === 'mix')
    ? sel(lightCornice, wallColor.mul(1.08).add(0.03),
      sel(mixCornice, mix(wallColor, vec3(0.62, 0.58, 0.5), 0.55), vec3(0.06, 0.055, 0.05).add(wallColor.mul(0.15))))
    : sel(lightCornice, wallColor.mul(1.08).add(0.03), vec3(0.06, 0.055, 0.05).add(wallColor.mul(0.15)));
  wall = mix(wall, corniceColor, anyBays ? cornice.mul(float(1).sub(berCornice)) : cornice);
  // London: the cornice is the lower part of the top band, a parapet over it (brick a shade darker, stone and
  // stucco a balustrade on some: balusters against shade)
  if (uses((d) => d.cornice?.parapet)) {
    const parapet = cornice.mul(f01(where((d) => d.cornice?.parapet))).mul(smoothstep(wallH.sub(corniceH.mul(0.55)).sub(fyM), wallH.sub(corniceH.mul(0.55)), y));
    const balustrade = f01(users((d) => d.cornice?.balustrade).reduce((acc, name) => {
      const share = styleData[name].cornice.balustrade, t = share === 1 ? is(name) : is(name).and(h1(seed.mul(15.1)).lessThan(share));
      return acc ? acc.or(t) : t;
    }, null))
      .mul(band(y, wallH.sub(corniceH.mul(0.45)), wallH.sub(0.18), fyM))
      .mul(stripe(s.div(0.3), float(0.55), float(1), max(fwidth(s), 1e-3).div(0.3)));
    const parC = sel(where((d) => d.cornice?.parapet === 'light'), wallColor.mul(1.02), wallColor.mul(0.9));
    wall = mix(wall, mix(parC, wallColor.mul(0.45), balustrade.mul(0.85)), parapet);
  }
  const cell = hash2(col, row.add(seed.mul(437.585)));
  const pane = mix(vec3(0.012, 0.014, 0.018), vec3(0.05, 0.05, 0.048), cell)
    .add(sel(cell.greaterThan(0.82), vec3(0.16, 0.14, 0.11), vec3(0, 0, 0))).add(vec3(0.01, 0.012, 0.016));
  let wallDetailed = mix(mix(mix(wall, frameColor, frameMask), vec3(0.55, 0.55, 0.53), ac), vec3(0.03, 0.03, 0.03), ironwork);
  // faubourg and small houses: shutters beside the windows (fewer on tall blocks), white, grey-green, blue-grey,
  // brown or olive per building, some closed over the window
  const hasShut0 = where((d) => d.shutters).and(h1(seed.mul(44.1)).lessThan(sel(height.greaterThan(15), float(0.3), float(0.7))))
    .and(ground.not()).and(onWall).and(isRoof.not());
  const hasShut = sgOpen ? hasShut0.and(noOpen.not()) : hasShut0;
  const shutW = xhi.sub(xlo).mul(0.48);
  const shutY = band(cy, ylo, yhi, wy);
  const shutSide = f01(hasShut).mul(shutY).mul(band(cx, xlo.sub(shutW), xlo, wx).add(band(cx, xhi, xhi.add(shutW), wx)));
  const shutClosed = f01(hasShut.and(h1(col.mul(3.7).add(row.mul(9.1)).add(seed.mul(5.3))).lessThan(0.2))).mul(open);
  const sk = h1(seed.mul(71.3));
  const shutColor = sel(sk.lessThan(0.3), vec3(0.8, 0.79, 0.73), sel(sk.lessThan(0.5), vec3(0.32, 0.38, 0.32),
    sel(sk.lessThan(0.7), vec3(0.19, 0.27, 0.35), sel(sk.lessThan(0.85), vec3(0.1, 0.06, 0.035), vec3(0.14, 0.16, 0.1)))))
    .mul(stripe(y.div(0.08), float(0), float(0.6), fyM.div(0.08)).mul(0.25).add(0.8));
  if (hasShutters) wallDetailed = mix(wallDetailed, shutColor, shutSide);

  // ---- roofs (facade/roofs.js)
  const { roofColor, slopeColor, zincRoof, blueSteel } = roofLook({ seed, height, y, s, X, fx, col, fyM, wallH, wallColor, hasRoof,
    // (styles.js roof.wall, opt-in: the roof in the wall's own colour, as a spire's; Hong Kong's Cultural Centre, whose
    // tiled ski-slope roofs read as grey concrete where flatter than the wall test; no other city's shader changes)
    roofMat, roofRise, roofCodes, brisis, isFactory, isVillage, isSpire: uses((d) => d.roof?.wall) ? isSpire.or(where((d) => d.roof?.wall)) : isSpire, isMon, NONE, slateMetal: where((d) => d.roof?.metal === 'slate'),
    flatStyles: where((d) => d.roof?.flat), dormersEvery: where((d) => d.roof?.dormers === 'every') }, roofs);

  // ---- far away the window grid of ordinary walls is smaller than a pixel: fade to its average instead
  // of shimmering (curtain walls filter their own patterns above)
  const cover0 = xhi.sub(xlo).mul(yhi.sub(ylo));
  const cover = sgOpen ? cover0.mul(float(1).sub(f01(noOpen))) : cover0;
  // (facade.farFade: where the grid starts and ends fading, in bays or floors a pixel; Singapore's HDB and condo blocks
  // speckled black at mid distance with the default)
  const far = smoothstep(float(farFade[0]), float(farFade[1]), max(wx, wy));
  const fwUV = max(fwidth(U), fwidth(Vc));
  const patternFar = smoothstep(float(0.15), float(0.4), fwUV.div(cellSize));
  const patternAvg0 = sel(isLattice, mix(tint.mul(0.45), white, seed.mul(0.8).add(0.2)),
    sel(isHoney, mix(tint, tint.mul(0.3), seed.mul(0.8)), tint.mul(0.95)));
  // (portholes: about 0.3 of the cell is window)
  const patternAvg = usePort ? sel(isPort, mix(tint.mul(0.93), vec3(0.05, 0.06, 0.07), f01(isRoof.not()).mul(0.3)), patternAvg0) : patternAvg0;
  const nearWall0 = mix(wallDetailed, pane, anyNone ? glassMask.mul(float(1).sub(ironwork)).mul(float(1).sub(wareDoor)) : glassMask.mul(float(1).sub(ironwork)));
  const nearWall = hasShutters ? mix(nearWall0, shutColor, shutClosed) : nearWall0;
  const farWall = mix(mix(wall, vec3(0.03, 0.032, 0.036), cover.mul(0.85).mul(f01(onWall))), vec3(0.03, 0.03, 0.03),
    hasBalc ? escape.mul(0.25).add(f01(balcRow).mul(0.12)) : escape.mul(0.25));
  // ---- monuments (the monument style, landmark_facades.csv): cut stone without the housing grid. The style
  // parameter picks the kind by fifths: 0 an arcade (round-arched bays between paired columns, a gilt band under
  // the cornice: the Opéra), 1 a palace (tall arched windows between pilasters: the Louvre, the Hôtel de Ville),
  // 2 gothic (narrow lancets between buttresses, portals at the foot, a louvred belfry in the top third of a tower
  // over 55 m: Notre-Dame), 3 blank ashlar with an entablature and an attic (the Arc de Triomphe), 4 a steel frame
  // over glass with coloured service ducts on its east face and an escalator's diagonal on its west face (the Centre
  // Pompidou; one bay per module, the style parameter 0.8+). In a branch
  // (only its own walls pay for it) built from copies of its inputs; far away it fades to its average
  const monOut = uses((d) => d.monument) ? Fn(() => {
    const V = Object.fromEntries(Object.entries({ cx, cy, y, wx, wy, fyM, seed, height, wallH, far, row, col, fh, wall, s,
      runLen, bayW: runLen.div(bays), nx: normalWorldGeometry.x }).map(([k, n]) => [k, n.toVar()]));
    const out = vec3(0).toVar();
    If(isMon.and(isRoof.not()), () => {
      const kind = floor(V.seed.mul(5));
      const arcade = kind.lessThan(0.5), palace = kind.equal(1), gothic = kind.equal(2), blank = kind.equal(3), frame = kind.greaterThan(3.5);
      // the blank kind's lower half (style parameter 0.6-0.69): a peristyle, free-standing columns one per bay on a
      // podium, the cella's shaded wall between them (the Madeleine); 0.7+ stays the Arc's blank ashlar
      const colonnade = blank.and(fract(V.seed.mul(5)).lessThan(0.45));
      // the gothic kind's top (style parameter 0.54-0.59): Perpendicular, the Palace of Westminster's walls: wide
      // mullioned windows, the wall between them panelled in thin vertical ribs, no rose, portal or belfry
      const perp = gothic.and(fract(V.seed.mul(5)).greaterThan(0.69));
      // the blank kind's top (style parameter 0.74-0.79): a power station's brick, tall narrow slot windows one per
      // bay from a tenth to nine tenths of the wall, no floor grid, no bands (Tate Modern, London M10b)
      const slots = blank.and(fract(V.seed.mul(5)).greaterThan(0.69));
      const pm = max(max(V.wx.mul(V.bayW), V.wy.mul(V.fh)), 0.02);                     // metres per pixel
      const dx = V.cx.sub(0.5).mul(V.bayW), adx = abs(dx), yy = V.cy.mul(V.fh);
      // the opening: a rectangle from the sill, a round arch (a pointed one on gothic walls) on top
      const hw = V.bayW.mul(sel(perp, float(0.3), sel(gothic, float(0.16), sel(arcade, float(0.3), float(0.2)))));
      const sill = V.fh.mul(sel(arcade, float(0.02), sel(perp, float(0.1), float(0.16))));
      // (Perpendicular: a flat four-centred head, tall lights under it)
      const rise = sel(perp, float(0.45), float(1.6));
      const spring = V.fh.mul(sel(perp, float(0.86), float(0.8))).sub(hw.mul(sel(gothic, rise, float(1))));
      const dRound = sel(yy.lessThan(spring), max(adx.sub(hw), sill.sub(yy)), length(vec2(dx, yy.sub(spring))).sub(hw));
      const dPoint = max(max(adx.sub(hw), sill.sub(yy)), yy.sub(spring).sub(hw.sub(adx).mul(rise)));
      const openM = float(1).sub(smoothstep(pm.negate(), pm, sel(gothic, dPoint, dRound))).mul(f01(blank.not()))
        .mul(float(1).sub(smoothstep(V.wallH.sub(3.5), V.wallH.sub(3.4), V.y)));     // none in the entablature
      // gothic: portals (deep pointed recesses at the foot of a front), the belfry's louvred openings
      // (on fronts, the short runs: the west front, the towers, the transepts; not along the nave)
      const front = gothic.and(perp.not()).and(V.runLen.lessThan(40)).and(V.height.greaterThan(25));
      const portal = f01(front.and(V.row.lessThan(0.5)))
        .mul(float(1).sub(smoothstep(pm.negate(), pm, max(adx.sub(V.bayW.mul(0.36)), yy.sub(V.fh.mul(0.55)).sub(V.bayW.mul(0.36).sub(adx).mul(1.4))))));
      const belfryY = V.y.sub(V.height.mul(0.6)).div(V.height.mul(0.3));
      const belfry = f01(gothic.and(perp.not()).and(V.height.greaterThan(55))).mul(band(belfryY, float(0), float(1), V.fyM.div(V.height.mul(0.3))))
        .mul(float(1).sub(smoothstep(pm.negate(), pm, adx.sub(V.bayW.mul(0.3)))));
      const slats = stripe(V.y.div(0.5), float(0), float(0.35), V.fyM.div(0.5)).mul(0.5).add(0.5);
      // pilasters (palace), paired columns (arcade), buttresses (gothic) at the bay edges, lit and shaded
      const edge = min(V.cx, float(1).sub(V.cx)).mul(V.bayW);
      const colX = adx.sub(hw);
      const column = f01(arcade).mul(band(colX, float(0.25), float(0.75), pm).add(band(colX, float(0.95), float(1.45), pm)));
      const pilaster = f01(palace).mul(band(edge, float(-1), float(0.45), pm));
      const buttress = f01(gothic).mul(band(edge, float(-1), float(0.7), pm));
      // courses of ashlar (0.55 m), fading with distance
      const joint = stripe(V.y.div(0.55), float(0), float(0.06), V.fyM.div(0.55)).mul(float(1).sub(smoothstep(float(0.04), float(0.2), V.fyM)));
      // entablature: a cornice lip and a frieze under it; gilt on the arcade; the blank kind's attic panels
      const cornice = band(V.y, V.wallH.sub(1.2), V.wallH.sub(0.2), V.fyM);
      const frieze = band(V.y, V.wallH.sub(3.4), V.wallH.sub(1.9), V.fyM);
      const gilt = f01(arcade).mul(band(V.y, V.wallH.sub(3.1), V.wallH.sub(2.3), V.fyM));
      const midBand = f01(blank.and(colonnade.not()).and(slots.not())).mul(band(V.y, V.height.mul(0.585), V.height.mul(0.62), V.fyM)
        .add(band(V.y, V.height.mul(0.67), V.height.mul(0.69), V.fyM)));
      const stone = V.wall.mul(float(1).sub(joint.mul(0.08)));
      let c = mix(stone, V.wall.mul(1.12), column.add(pilaster).clamp(0, 1));
      c = mix(c, V.wall.mul(0.72), buttress.mul(sel(V.cx.lessThan(0.5), float(1), float(0.6))));
      c = mix(c, V.wall.mul(1.1), cornice);
      c = mix(c, V.wall.mul(0.78), frieze.add(midBand).clamp(0, 1));
      c = mix(c, vec3(0.52, 0.36, 0.1), gilt);
      c = mix(c, V.wall.mul(0.42), portal);
      // peristyle: podium to 20 % of the wall, columns (a fifth of the bay to each side of its centre, rounded by a
      // light-to-shade ramp, a capital under the entablature) over the shaded cella wall
      const podium = V.wallH.mul(0.2), capY = V.wallH.sub(3.4);
      const inCols = f01(colonnade).mul(band(V.y, podium, capY, V.fyM));
      const cr = V.bayW.mul(0.19), u = dx.div(cr);
      const shaft = float(1).sub(smoothstep(cr.sub(pm), cr.add(pm), adx));
      const capital = band(V.y, capY.sub(1.2), capY, V.fyM).mul(float(1).sub(smoothstep(cr.mul(1.25).sub(pm), cr.mul(1.25).add(pm), adx)));
      const colM = shaft.max(capital);
      const roundK = float(1.18).sub(u.mul(u).mul(0.45)).sub(u.mul(0.12));
      const flute = stripe(dx.div(0.3), float(0), float(0.5), pm.div(0.3)).mul(0.06).mul(float(1).sub(smoothstep(float(0.05), float(0.15), pm)));
      c = mix(c, mix(V.wall.mul(0.4), V.wall.mul(roundK.sub(flute)), colM), inCols);
      c = mix(c, V.wall.mul(1.06), f01(colonnade).mul(band(V.y, podium.sub(0.6), podium, V.fyM)));
      // a rose window in the middle of a front up to 45 m high: a dark disc with light tracery (spokes, a ring)
      const rr = V.wallH.mul(0.15).min(V.runLen.mul(0.3));
      const rv = vec2(V.s.sub(V.runLen.mul(0.5)), V.y.sub(V.wallH.mul(0.66)));
      const rd = length(rv);
      const roseOn = f01(front.and(V.height.lessThan(45)).and(V.runLen.greaterThan(9)));
      const rose = roseOn.mul(float(1).sub(smoothstep(rr.sub(pm), rr.add(pm), rd)));
      const spokes = abs(fract(atan(rv.y, rv.x).mul(16 / 6.2832)).sub(0.5)).mul(rd).mul(6.2832 / 16);
      const tracery = rose.mul(float(1).sub(smoothstep(float(0.12), float(0.12).add(pm), spokes)).max(band(rd, rr.mul(0.3), rr.mul(0.36), pm)));
      const recess = sel(arcade, vec3(0.05, 0.045, 0.04), vec3(0.03, 0.032, 0.036));
      c = mix(c, recess, openM.mul(float(1).sub(portal)).mul(float(1).sub(roseOn.mul(band(V.y, V.wallH.mul(0.66).sub(rr).sub(1), V.wallH.mul(0.66).add(rr).add(1), pm)))));
      c = mix(c, vec3(0.035, 0.033, 0.03).mul(slats), belfry);
      // Perpendicular: ribs every sixth of a bay over the wall and mullions (a third of the opening) with a transom
      // across the windows, both fading out with distance into the wall's average
      const fadeP = float(1).sub(smoothstep(float(0.05), float(0.25), pm));
      const rib = stripe(V.s.div(V.bayW.div(6)), float(0), float(0.16), pm.div(V.bayW.div(6)));
      const mullion = stripe(dx.div(hw.mul(0.667)).add(0.5), float(0), float(0.12), pm.div(hw.mul(0.667)))
        .max(band(yy, spring.mul(0.55), spring.mul(0.55).add(0.25), pm));
      const course = band(V.cy, float(0.0), float(0.035), V.wy);
      c = mix(c, V.wall.mul(0.78), f01(perp).mul(rib.max(course)).mul(float(1).sub(openM)).mul(fadeP));
      c = mix(c, V.wall.mul(0.62), f01(perp).mul(mullion).mul(openM).mul(fadeP));
      c = mix(mix(c, vec3(0.04, 0.045, 0.07), rose), V.wall.mul(0.8), tracery);
      const slotM = f01(slots).mul(float(1).sub(smoothstep(pm.negate(), pm, adx.sub(V.bayW.mul(0.07)))))
        .mul(band(V.y, V.wallH.mul(0.1), V.wallH.mul(0.9), V.fyM));
      c = mix(c, vec3(0.045, 0.05, 0.055), slotM);
      const avg = V.wall.mul(sel(arcade, float(0.72), sel(palace, float(0.82), sel(gothic, float(0.85), sel(colonnade, float(0.75), sel(slots, float(0.88), float(0.95)))))));
      // the steel frame: columns at the bay edges, a beam at each floor, a cross brace in every bay, over dark glass
      const mEdge = min(V.cx, float(1).sub(V.cx)).mul(V.bayW), fEdge = min(V.cy, float(1).sub(V.cy)).mul(V.fh);
      const brace = min(abs(V.cx.sub(V.cy)), abs(V.cx.add(V.cy).sub(1))).mul(V.bayW);
      const steel = float(1).sub(smoothstep(float(0.35).sub(pm), float(0.35).add(pm), min(min(mEdge, fEdge), brace)));
      let f = mix(vec3(0.045, 0.055, 0.065), V.wall, steel);
      // east face: ducts in blue, green, yellow and red, one per bay across its middle; west face: the escalator
      const duct = f01(V.nx.greaterThan(0.6)).mul(band(V.cx, float(0.3), float(0.7), V.wx));
      const dk = floor(V.col).mod(4);
      const ductC = sel(dk.lessThan(0.5), vec3(0.03, 0.12, 0.45), sel(dk.lessThan(1.5), vec3(0.07, 0.3, 0.08),
        sel(dk.lessThan(2.5), vec3(0.72, 0.52, 0.03), vec3(0.6, 0.04, 0.02))));
      const esc = f01(V.nx.lessThan(-0.6)).mul(band(fract(V.y.sub(V.s.mul(0.32)).div(V.fh.mul(2))), float(0), float(0.16), V.fyM.div(V.fh.mul(2)).add(0.01)));
      f = mix(mix(f, ductC, duct), vec3(0.72, 0.73, 0.75), esc.mul(0.85));
      c = sel(frame, f, c);
      const avgF = mix(vec3(0.045, 0.055, 0.065), V.wall, 0.45);
      out.assign(mix(c, sel(frame, avgF, avg), V.far.mul(0.8)));
    });
    return out;
  })() : null;

  // ---- the near detail of ordinary walls (window frames and panes, railings, air conditioners, ironwork,
  // shutters) in a branch: it only shows where the window grid is resolved (far < 1), and never on roofs, curtain
  // walls or patterned skins, so the overview's walls, all past the fade, skip it. The branch rebuilds its nodes
  // from copies of its inputs taken before it (a node shared with the rest of the shader and first built inside
  // the branch would be set only there: see tsl-and-three-pitfalls.md), and takes no derivatives (fwidth is only
  // defined in uniform control flow): wx, wy, fx, fy, fyM are taken before. ?facade-branch=0: no branch
  const branch = !/[?&]facade-branch=0/.test(globalThis.location?.search ?? '');
  // a window pane's dark interior, its own shade per window, one in six warmly lit (V: the branch's copies)
  const bPane0 = (V) => {
    const bCell = hash2(V.col, V.row.add(V.seed.mul(437.585)));
    return mix(vec3(0.012, 0.014, 0.018), vec3(0.05, 0.05, 0.048), bCell)
      .add(sel(bCell.greaterThan(0.82), vec3(0.16, 0.14, 0.11), vec3(0, 0, 0))).add(vec3(0.01, 0.012, 0.016));
  };
  // the glazing types of the near detail (styles.js glazing; the preset's facade.shopfront): sash and casement windows
  // with their bars, reveals and the shop windows' transoms (London's), Kastenfenster and post-war stiles, net curtains
  // and drapes, shop interiors with shelves, awnings, the French balconies' railings (Berlin's)
  const sashNear = uses((d) => d.glazing === 'sash' || d.glazing === 'casement') || uses((d) => d.reveals);
  const kastenNear = uses((d) => ['kasten', 'stile', 'office'].includes(d.glazing)) || uses((d) => d.frenchBalconies) || SF.interior === 'shelves';
  // lived-in windows (styles.js livedInWindows: Hong Kong's flats, M4 fix round 1): sliding windows with a meeting stile,
  // and per window curtains, blinds, an open sash, a window air conditioner or iron grilles
  const livedNear = uses((d) => d.livedInWindows);
  const nearOut = branch && Fn(() => {
    const V = Object.fromEntries(Object.entries({ wall, xlo, xhi, ylo, yhi, cx, cy, wx, wy, fx, fy, fyM, X, F, row, col, seed, y,
      height, nearTop, cornice, escape, style: style, ground: f01(ground), balcony: f01(balcony), onWall: f01(onWall),
      balcRow: f01(balcRow), wareDoor, frameT, frameLight, sash: byValue((d) => ({ sash: 1, casement: 2 })[d.glazing], 0),
      lonMas: uses((d) => d.reveals) ? f01(where((d) => d.reveals)) : float(0),
      // (Berlin's only: other cities' shaders keep the inputs they had)
      ...(kastenNear ? { berWin: byValue((d) => ({ kasten: 2, stile: 1, office: 0.7 })[d.glazing], 0),
        altBalc: f01(altBalc) } : {}),
      ...(livedNear ? { lived: f01(where((d) => d.livedInWindows)) } : {}),
      openOK: sel(sgOpen ? isPlain.or(isRoof).or(isSpire).or(isFlood).or(isMon).or(onWall.not()).or(noOpen)
        : isPlain.or(isRoof).or(isSpire).or(isFlood).or(isMon).or(onWall.not()), float(0), float(1)) })
      .map(([k, n]) => [k, n.toVar()]));
    const out = vec4(0).toVar();
    If(far.lessThan(1).and(isPattern.not()).and(isCurtain.not()).and(isRoof.not()), () => {
      const isV = (name) => (ID[name] === undefined ? NONE : V.style.equal(ID[name]));
      const onGround = V.ground.greaterThan(0.5), onBalcony = V.balcony.greaterThan(0.5), wallHere = V.onWall.greaterThan(0.5);
      const bOpen = band(V.cx, V.xlo, V.xhi, V.wx).mul(band(V.cy, V.ylo, V.yhi, V.wy))
        .mul(float(1).sub(V.nearTop)).mul(float(1).sub(V.cornice)).mul(V.openOK);
      const bRail = V.balcony.mul(band(V.cy, float(0.06), float(0.38), V.wy).mul(band(V.cx, V.xlo, V.xhi, V.wx)));
      // (Berlin: the Altbau's broad wooden casement frames)
      const fwX = kastenNear ? sel(V.berWin.greaterThan(1.5), float(0.05), float(0.035)) : 0.035;
      const fwY = kastenNear ? sel(V.berWin.greaterThan(1.5), float(0.055), float(0.045)) : 0.045;
      const bInner = band(V.cx, V.xlo.add(fwX), V.xhi.sub(fwX), V.wx).mul(band(V.cy, V.ylo.add(fwY), V.yhi.sub(fwY), V.wy));
      const noDoor = anyNone ? float(1).sub(V.wareDoor) : float(1);
      const bFrame = bOpen.sub(bInner.mul(bOpen)).max(0).mul(noDoor);
      let bGlass = bOpen.sub(bFrame).mul(float(1).sub(bRail)).max(0).mul(noDoor);
      const bFrameColor = sel(h1(V.seed.mul(5.3)).greaterThan(V.frameT), V.frameLight, vec3(0.09, 0.09, 0.1));
      // London's sash windows: a meeting rail across the middle and glazing bars (six over six, box-filtered;
      // fine bars fade before they shimmer)
      let bBars = float(0), bReveal = float(0);
      if (sashNear) {
        const wc = windowCoords(V, 0.04, 0.12);
        // (sashes six over six; Portland stone offices' casements two lights under a transom; core windowBars)
        bBars = windowBars(wc, 'sash', { sash: V.sash, gate: f01(onGround.not()) });
        // shopfronts: a transom with clerestory lights over the display window, a mullion in the middle
        bBars = max(bBars, shopWindowBars(wc, SF.bars, f01(onGround)));
        // reveals: the masonry's depth, a shaded strip inside the top and one side of each opening
        const rv = float(1).sub(band(V.cx, V.xlo, V.xhi.sub(0.05), V.wx).mul(band(V.cy, V.ylo, V.yhi.sub(0.06), V.wy)));
        bReveal = rv.mul(V.lonMas).mul(f01(onGround.not()));
      }
      // Berlin (M4 fix round: the windows read as black holes, the shopfronts as black bands): the Kastenfenster's
      // meeting stile and the transom under its fanlight (post-war windows: a stile at two thirds), net curtains
      // (Gardinen) behind four windows in ten and drapes at the sides of two, the Altbau balconies' iron railings;
      // shops: lit interiors with shelves, a display window's mullion and transom, an awning over two in five
      // (in branches: the glass's own detail where there is glass, the awnings and railings where there are any; the
      // stone between the windows pays for none of it)
      let berBars = float(0), berIron = float(0), berAwn = float(0), berAwnC = vec3(0), berPane = null;
      if (kastenNear) {
        const bars = float(0).toVar(), iron = float(0).toVar(), awn = float(0).toVar(), awnC = vec3(0).toVar(), paneV = bPane0(V).toVar();
        const old = V.berWin.greaterThan(1.5), anyW = V.berWin.greaterThan(0.5);
        const homeW = V.berWin.greaterThan(0.9).and(onGround.not());     // (offices: no curtains)
        const awnOn = onGround.and(h1(floor(V.col.div(2)).add(V.seed.mul(41.3))).lessThan(SF.awnings ?? 0));
        If(bOpen.greaterThan(0.001), () => {
          const wc = windowCoords(V, 0.05, 0.14), { wu, wv, du, dv, fine } = wc;
          const tr = sel(V.altBalc.greaterThan(0.5), float(0.8), float(0.72));
          const winBars = windowBars(wc, 'kasten', { stileAt: sel(old, float(0.5), float(0.64)), tr, old, gate: f01(anyW.and(onGround.not())) });
          bars.assign(max(winBars, shopWindowBars(wc, SF.bars, f01(onGround))));
          // curtains
          const ck = h1(V.col.mul(5.1).add(V.row.mul(13.7)).add(V.seed.mul(3.3)));
          const net = f01(ck.lessThan(0.4).and(homeW)).mul(f01(wv.lessThan(sel(old, tr, float(1.01)))))
            .mul(stripe(wu.mul(14), float(0), float(0.55), du.mul(14)).mul(0.25).add(0.75));
          const drapeW = sel(ck.lessThan(0.5), float(0.22), float(0.16));
          const drape = f01(ck.greaterThan(0.4).and(ck.lessThan(0.52)).and(homeW))
            .mul(band(wu, float(-0.1), drapeW, du).add(band(wu, float(1).sub(drapeW), float(1.1), du)).min(1));
          const dk = h1(V.col.mul(2.3).add(V.seed.mul(9.7)));
          const drapeC = sel(dk.lessThan(0.2), vec3(0.2, 0.07, 0.055), sel(dk.lessThan(0.6), vec3(0.4, 0.35, 0.26),
            sel(dk.lessThan(0.75), vec3(0.1, 0.13, 0.09), vec3(0.28, 0.28, 0.27))));
          // shop interiors: lit, warm, shelves
          const sCell = h1(floor(V.col.div(2)).add(V.seed.mul(23.9)));
          const shelves = stripe(wv.mul(5), float(0), float(0.14), dv.mul(5));
          const shopIn = mix(vec3(0.16, 0.13, 0.095), vec3(0.3, 0.27, 0.22), sCell).mul(float(1).sub(shelves.mul(0.45).mul(fine)));
          const awnShade = f01(awnOn).mul(band(V.cy, V.yhi.sub(0.32), V.yhi.sub(0.2), V.wy));
          const paneB = mix(mix(bPane0(V), vec3(0.4, 0.4, 0.37), net.mul(0.8)), drapeC, drape.mul(0.92));
          paneV.assign(mix(paneB, shopIn.mul(float(1).sub(awnShade.mul(0.5))), f01(onGround)));
        });
        // awnings: over two shops in five, the top fifth of the window, striped or plain, lit on top, shading the glass
        If(awnOn, () => {
          const ak = h1(floor(V.col.div(2)).add(V.seed.mul(5.77)));
          const awnBase = sel(ak.lessThan(0.25), vec3(0.4, 0.04, 0.03), sel(ak.lessThan(0.45), vec3(0.03, 0.16, 0.07),
            sel(ak.lessThan(0.6), vec3(0.03, 0.06, 0.2), sel(ak.lessThan(0.8), vec3(0.6, 0.55, 0.42), vec3(0.06, 0.06, 0.065)))));
          const awnStripes = f01(h1(V.seed.mul(29.3).add(floor(V.col.div(2)))).lessThan(0.4)).mul(stripe(V.X.mul(10), float(0), float(0.5), V.fx.mul(10)));
          awn.assign(band(V.cy, V.yhi.sub(0.2), V.yhi.add(0.04), V.wy).mul(band(V.cx, float(-0.02), float(1.02), V.wx)));
          const awnT = clamp(V.cy.sub(V.yhi.sub(0.2)).div(0.24), 0, 1);
          awnC.assign(mix(awnBase, vec3(0.78, 0.76, 0.7), awnStripes.mul(0.85)).mul(mix(float(0.6), float(1.15), awnT)));
        });
        // Altbau balconies: an iron railing in front of the French door and across the slab, balusters every 12 cm
        If(V.altBalc.greaterThan(0.5), () => {
          const railX = band(V.cx, V.xlo.sub(0.13), V.xhi.add(0.13), V.wx);
          const rails = band(V.cy, float(0.27), float(0.3), V.wy).add(band(V.cy, float(0.035), float(0.05), V.wy));
          const balust = band(V.cy, float(0.035), float(0.3), V.wy).mul(stripe(V.X.mul(24), float(0), float(0.28), V.fx.mul(24)).mul(0.9).add(0.05));
          iron.assign(railX.mul(clamp(rails.add(balust), 0, 1)));
        });
        berBars = bars; berIron = iron; berAwn = awn; berAwnC = awnC; berPane = paneV;
      }
      // lived-in windows: per window (by its hash) curtains drawn part way (pale fabric, folds), slatted blinds from the
      // top, one sash slid open (that half dark, no glass), a window air conditioner in the lower part (a beige box with
      // a grille), and on some flats iron grilles over the whole window; a meeting stile down the middle of every one
      let livPane = null, livOver = null, livOverC = null, livGlass = null;
      if (livedNear) {
        const paneV = bPane0(V).toVar(), over = float(0).toVar(), overC = vec3(0).toVar(), glassK = float(1).toVar();
        If(bOpen.greaterThan(0.001).and(V.lived.greaterThan(0.5)).and(onGround.not()), () => {
          const { wu, wv, du, dv, fine } = windowCoords(V, 0.05, 0.16);
          const ck = h1(V.col.mul(5.1).add(V.row.mul(13.7)).add(V.seed.mul(3.3)));
          const fk = h1(V.col.mul(2.3).add(V.row.mul(7.9)).add(V.seed.mul(9.7)));
          const fabric = sel(fk.lessThan(0.3), vec3(0.62, 0.6, 0.54), sel(fk.lessThan(0.5), vec3(0.42, 0.5, 0.56),
            sel(fk.lessThan(0.65), vec3(0.6, 0.44, 0.42), sel(fk.lessThan(0.8), vec3(0.5, 0.52, 0.4), vec3(0.58, 0.46, 0.26)))));
          // curtains: from one side (by fk) to a share of the width, faint folds
          const reach = fk.mul(0.6).add(0.4);
          const side = sel(fk.lessThan(0.5), wu, float(1).sub(wu));
          const curtain = f01(ck.lessThan(0.3)).mul(band(side, float(-0.1), reach, du));
          const folds = stripe(wu.mul(9), float(0), float(0.5), du.mul(9)).mul(fine).mul(0.18).add(0.82);
          const blind = f01(ck.greaterThan(0.3).and(ck.lessThan(0.38))).mul(band(wv, float(1).sub(reach.mul(0.8)), float(1.1), dv))
            .mul(stripe(wv.mul(14), float(0), float(0.75), dv.mul(14)).mul(fine).mul(0.3).add(0.7));
          const openHalf = f01(ck.greaterThan(0.38).and(ck.lessThan(0.52))).mul(band(side, float(-0.1), float(0.5), du));
          const pane = mix(mix(bPane0(V), fabric.mul(folds), curtain), vec3(0.55, 0.55, 0.52), blind);
          paneV.assign(mix(pane, vec3(0.012, 0.011, 0.01), openHalf));
          // window air conditioner: the lower 40 % of one half, beige or grey, its grille lines, its shadow under it
          const acW = f01(ck.greaterThan(0.52).and(ck.lessThan(0.66))).mul(band(side, float(0.02), float(0.52), du))
            .mul(band(wv, float(0.0), float(0.42), dv));
          const acC = sel(fk.lessThan(0.6), vec3(0.6, 0.58, 0.52), vec3(0.5, 0.51, 0.5))
            .mul(stripe(wv.mul(24), float(0), float(0.4), dv.mul(24)).mul(fine).mul(0.25).add(0.8));
          // iron grilles (two flats in five on some buildings): bars every eighth of the width, rails at a third
          const grilled = h1(V.seed.mul(19.7)).lessThan(0.5).and(h1(V.col.add(V.row.mul(3.3)).add(V.seed.mul(41.1))).lessThan(0.45));
          const bars = clamp(stripe(wu.mul(8), float(0), float(0.14), du.mul(8)).add(stripe(wv.mul(3), float(0), float(0.08), dv.mul(3))), 0, 1)
            .mul(f01(grilled)).mul(mix(float(0.45), float(1), fine));
          const grilleC = sel(h1(V.seed.mul(5.9)).lessThan(0.6), vec3(0.05, 0.05, 0.055), vec3(0.62, 0.62, 0.6));
          // the meeting stile of the sliding sashes, aluminium
          const stile = stripe(wu.add(0.5), float(0.48), float(0.52), du).mul(fine);
          const ov = clamp(acW.add(bars).add(stile), 0, 1);
          over.assign(ov);
          overC.assign(mix(mix(vec3(0.55, 0.56, 0.56), grilleC, bars), acC, acW));
          glassK.assign(float(1).sub(openHalf).mul(float(1).sub(acW)).mul(float(1).sub(curtain.mul(0.4))));
        });
        livPane = paneV; livOver = over; livOverC = overC; livGlass = glassK;
      }
      const bAcChance = pick(V.style, perStyle((d) => d.ac, 0));
      const bAcHere0 = h1(V.col.mul(7.13).add(V.row.mul(3.1)).add(V.seed.mul(11.7))).lessThan(bAcChance).and(onGround.not()).and(onBalcony.not());
      const bAcHere = sgOpen ? bAcHere0.and(V.openOK.greaterThan(0.5)) : bAcHere0;
      const bAcX = mix(V.xlo, V.xhi.sub(0.32), h1(V.col.add(V.seed.mul(5.9))));
      const bAc = sel(bAcHere, band(V.cx, bAcX, bAcX.add(0.3), V.wx).mul(band(V.cy, float(0.05), V.ylo.sub(0.04), V.wy)), float(0))
        .mul(float(1).sub(V.nearTop));
      let bIron = uses((d) => d.fireEscape) ? clamp(stripe(V.F, float(0), float(0.05), V.fy)
        .add(stripe(V.F, float(0.05), float(0.36), V.fy).mul(stripe(V.X.mul(8), float(0), float(0.25), V.fx.mul(8)).mul(0.8).add(0.1)))
        .add(stripe(V.F.add(V.X.mul(0.5)), float(0.46), float(0.52), max(V.fy, V.fx.mul(0.5))).mul(0.7)), 0, 1).mul(V.escape) : float(0);
      let bShutC = null, bShutSide = null, bShutClosed = null;
      if (hasBalc || hasGuard || hasShutters) {
        const bBalusters = stripe(V.X.mul(14), float(0), float(0.45), V.fx.mul(14)).mul(0.55).add(0.35);
        const bBalc = V.balcRow.mul(band(V.cy, float(0.0), float(0.3), V.wy)).mul(bBalusters);
        const bGuard = f01(where((d) => d.guardRails, isV).and(V.balcRow.lessThan(0.5)).and(V.row.greaterThan(1.5)).and(wallHere))
          .mul(band(V.cy, V.ylo, V.ylo.add(0.2), V.wy)).mul(band(V.cx, V.xlo, V.xhi, V.wx)).mul(bBalusters);
        bIron = max(bIron, max(bBalc, bGuard));
        let bHasShut = where((d) => d.shutters, isV).and(h1(V.seed.mul(44.1)).lessThan(sel(V.height.greaterThan(15), float(0.3), float(0.7))))
          .and(onGround.not()).and(wallHere);
        if (sgOpen) bHasShut = bHasShut.and(V.openOK.greaterThan(0.5));
        const bShutW = V.xhi.sub(V.xlo).mul(0.48);
        bShutSide = f01(bHasShut).mul(band(V.cy, V.ylo, V.yhi, V.wy))
          .mul(band(V.cx, V.xlo.sub(bShutW), V.xlo, V.wx).add(band(V.cx, V.xhi, V.xhi.add(bShutW), V.wx)));
        bShutClosed = f01(bHasShut.and(h1(V.col.mul(3.7).add(V.row.mul(9.1)).add(V.seed.mul(5.3))).lessThan(0.2))).mul(bOpen);
        const sk = h1(V.seed.mul(71.3));
        bShutC = sel(sk.lessThan(0.3), vec3(0.8, 0.79, 0.73), sel(sk.lessThan(0.5), vec3(0.32, 0.38, 0.32),
          sel(sk.lessThan(0.7), vec3(0.19, 0.27, 0.35), sel(sk.lessThan(0.85), vec3(0.1, 0.06, 0.035), vec3(0.14, 0.16, 0.1)))))
          .mul(stripe(V.y.div(0.08), float(0), float(0.6), V.fyM.div(0.08)).mul(0.25).add(0.8));
      }
      const bCell = hash2(V.col, V.row.add(V.seed.mul(437.585)));
      const bPane = mix(vec3(0.012, 0.014, 0.018), vec3(0.05, 0.05, 0.048), bCell)
        .add(sel(bCell.greaterThan(0.82), vec3(0.16, 0.14, 0.11), vec3(0, 0, 0))).add(vec3(0.01, 0.012, 0.016));
      if (kastenNear) bIron = max(bIron, berIron);
      let bDetailed = mix(mix(mix(V.wall, bFrameColor, bFrame), vec3(0.55, 0.55, 0.53), bAc), vec3(0.03, 0.03, 0.03), bIron);
      if (hasShutters) bDetailed = mix(bDetailed, bShutC, bShutSide);
      // (London's shop windows: a lit interior, warm grey, behind the glass)
      const bPaneL = SF.interior === 'warm' ? mix(bPane, vec3(0.07, 0.062, 0.05).add(vec3(0.05, 0.04, 0.03).mul(bCell)), f01(onGround)) : berPane ?? livPane ?? bPane;
      let bNear = mix(bDetailed, bPaneL, bGlass.mul(float(1).sub(bIron)));
      if (livedNear) {
        bNear = mix(bNear, livOverC, livOver.mul(bGlass));
        bGlass = bGlass.mul(livGlass).mul(float(1).sub(livOver));
      }
      if (sashNear) {
        const shopFrame = mix(bFrameColor, vec3(0.02, 0.02, 0.022), f01(onGround));
        bNear = mix(bNear, shopFrame, bBars.mul(bGlass));
        bNear = mix(bNear, V.wall.mul(0.5), bReveal.mul(bOpen));
        bGlass = bGlass.mul(float(1).sub(bReveal));
      }
      if (hasShutters) bNear = mix(bNear, bShutC, bShutClosed);
      if (kastenNear) {
        bNear = mix(bNear, sel(onGround, vec3(0.04, 0.04, 0.045), bFrameColor), berBars.mul(bGlass));
        bNear = mix(bNear, berAwnC, berAwn);
        bGlass = bGlass.mul(float(1).sub(berBars.mul(0.9))).mul(float(1).sub(berAwn));
      }
      out.assign(vec4(bNear, bGlass));
    });
    return out;
  })();
  const plainWall = branch ? mix(nearOut.xyz, farWall, far) : mix(nearWall, farWall, far);
  const glassNear = branch ? nearOut.w : glassMask;
  const facade0 = sel(isPattern, mix(patternColor, patternAvg, patternFar), sel(isCurtain, glassWall, monOut ? sel(isMon, monOut, plainWall) : plainWall));
  // vertical signboards (styles.js signboards: Tokyo's 雑居ビル): a stack of boards at one end of a narrow front (3-16 m
  // runs), over the finished wall and its windows, box-filtered so a far one is a coloured strip; lit after dark
  const signUse = uses((d) => d.signboards);
  // (in a branch only those fronts pay for, and only while a board is over half a pixel wide: built from copies of its
  // inputs, as monOut; computed for every wall pixel it cost Tokyo's overview 18 ms settled on WebGPU)
  const signboard = signUse ? (() => {
    const fsS = max(fwidth(s), 1e-3);
    const signOn = where((d) => d.signboards).and(onWall).and(isRoof.not()).and(runLen.greaterThan(3)).and(runLen.lessThan(16))
      .and(fsS.lessThan(1.6)).and(row.greaterThan(0.5));
    const inS = { s, runLen, y, row, cy, wy, fs: fsS, fyM, fh, wallH, seed };
    const o = Fn(() => {
      const S = Object.fromEntries(Object.entries(inS).map(([k, n]) => [k, n.toVar()]));
      const out = vec4(0).toVar();
      If(signOn, () => {
        const r = P.signboardStack({ ...S, on: S.row.greaterThan(0.5) });
        out.assign(vec4(r.colour, r.mask));
      });
      return out;
    })();
    return { colour: o.xyz, mask: o.w };
  })() : null;
  const facade = signUse ? mix(facade0, signboard.colour, signboard.mask) : facade0;

  // ---- billboards: panels 7-16 m wide in rows (every other row shifted), the row height per building (6 m
  // boards to 20 m "spectaculars"), in dark frames; below 4 m the shopfronts. Each board shows one of the
  // atlas's advertisements (billboards.js), a wide one or a tall one by its own shape, fitted to cover it
  // without stretching; mip-mapped, so far away the boards average to a bright, colourful band
  const bw = mix(float(7), float(16), h1(seed.mul(5.7)));
  const bh = mix(float(6), float(20), pow(h1(seed.mul(6.1)), float(2)));
  const brow = floor(y.sub(4).div(bh));
  const bcol = floor(s.div(bw).add(fract(brow.mul(0.5)).mul(1.3)));
  const bu = fract(s.div(bw).add(fract(brow.mul(0.5)).mul(1.3))), bv = fract(y.sub(4).div(bh));
  const bid = hash2(bcol.add(seed.mul(71.3)), brow.add(seed.mul(13.9)));
  const bfw = max(max(fwidth(bu), fwidth(bv)), 1e-4);
  const ar = bw.div(bh);                                      // board aspect (width over height)
  let img = vec3(0.4, 0.35, 0.38);
  if (billboards) {
    const A = ATLAS;
    const tallB = ar.lessThan(1);
    const ca = sel(tallB, float(A.tall.w / A.tall.h), float(A.wide.w / A.wide.h));     // cell aspect
    // fitted to the board's width (the lettering runs across), cropped or extended at the top and bottom
    // (where the art is background)
    const fu = bu;
    const fv = clamp(bv.sub(0.5).mul(ca.div(ar)).add(0.5), 0.01, 0.99);
    const nW = A.wide.cols * A.wide.rows, nT = A.tall.cols * A.tall.rows;
    const iw = floor(bid.mul(nW)), it = floor(fract(bid.mul(7.31)).mul(nT));
    const uW = iw.mod(A.wide.cols).add(fu).mul(A.wide.w / A.size);
    const vW = float(1).sub(floor(iw.div(A.wide.cols)).add(float(1).sub(fv)).mul(A.wide.h / A.size));
    const uT = it.mod(A.tall.cols).add(fu).mul(A.tall.w / A.size);
    const vT = float(1).sub(floor(it.div(A.tall.cols)).mul(A.tall.h).add(A.tall.y0).add(float(1).sub(fv).mul(A.tall.h)).div(A.size));
    const auv = vec2(sel(tallB, uT, uW), sel(tallB, vT, vW));
    // the mip level from the board's size on screen (the per-cell fract would make the automatic one spike)
    const lod = log2(max(bfw.mul(A.wide.w), 1));
    img = texture(billboards, auv).level(lod).rgb;
  }
  const frameB = float(1).sub(band(bu, float(0.02), float(0.98), bfw).mul(band(bv, float(0.04), float(0.96), bfw)));
  const billboardFar = smoothstep(float(0.2), float(0.6), bfw);
  let board = mix(img, vec3(0.02, 0.02, 0.025), frameB.mul(float(1).sub(billboardFar)));
  // (facade.billboardBranch, Tokyo M4 fix round: the boards built in a branch only the signs style's walls under their
  // band pay for, from copies of their inputs, the derivatives taken outside it (the board's from the wall's own: no
  // spike at the cells' edges); computed for every wall pixel they cost Tokyo's Ginza street ~125 ms settled on WebGL 2
  // with not one board in view. Off: the shader every city had)
  if (billboardBranch && uses((d) => d.billboards)) {
    const dS = max(fwidth(s), 1e-4), dY = max(fwidth(y), 1e-4);
    const inB = { seed, s, y, dS, dY };
    const hereB = onSigns.and(y.greaterThan(4));
    board = Fn(() => {
      const V = Object.fromEntries(Object.entries(inB).map(([k, n]) => [k, n.toVar()]));
      const o = vec3(0).toVar();
      If(hereB, () => {
        const bw = mix(float(7), float(16), h1(V.seed.mul(5.7)));
        const bh = mix(float(6), float(20), pow(h1(V.seed.mul(6.1)), float(2)));
        const brow = floor(V.y.sub(4).div(bh));
        const shift = fract(brow.mul(0.5)).mul(1.3);
        const bcol = floor(V.s.div(bw).add(shift));
        const bu = fract(V.s.div(bw).add(shift)), bv = fract(V.y.sub(4).div(bh));
        const bid = hash2(bcol.add(V.seed.mul(71.3)), brow.add(V.seed.mul(13.9)));
        const bfw = max(max(V.dS.div(bw), V.dY.div(bh)), 1e-4);
        const ar = bw.div(bh);
        let im = vec3(0.4, 0.35, 0.38);
        if (billboards) {
          const A = ATLAS;
          const tallB = ar.lessThan(1);
          const ca = sel(tallB, float(A.tall.w / A.tall.h), float(A.wide.w / A.wide.h));
          const fv = clamp(bv.sub(0.5).mul(ca.div(ar)).add(0.5), 0.01, 0.99);
          const nW = A.wide.cols * A.wide.rows, nT = A.tall.cols * A.tall.rows;
          const iw = floor(bid.mul(nW)), it = floor(fract(bid.mul(7.31)).mul(nT));
          const uW = iw.mod(A.wide.cols).add(bu).mul(A.wide.w / A.size);
          const vW = float(1).sub(floor(iw.div(A.wide.cols)).add(float(1).sub(fv)).mul(A.wide.h / A.size));
          const uT = it.mod(A.tall.cols).add(bu).mul(A.tall.w / A.size);
          const vT = float(1).sub(floor(it.div(A.tall.cols)).mul(A.tall.h).add(A.tall.y0).add(float(1).sub(fv).mul(A.tall.h)).div(A.size));
          im = texture(billboards, vec2(sel(tallB, uT, uW), sel(tallB, vT, vW))).level(log2(max(bfw.mul(A.wide.w), 1))).rgb;
        }
        const fr = float(1).sub(band(bu, float(0.02), float(0.98), bfw).mul(band(bv, float(0.04), float(0.96), bfw)));
        o.assign(mix(im, vec3(0.02, 0.02, 0.025), fr.mul(float(1).sub(smoothstep(float(0.2), float(0.6), bfw)))));
      });
      return o;
    })();
  }
  const signsHere = f01(onSigns.and(y.greaterThan(4)));
  const signs = uses((d) => d.billboards);
  const wallFacade = signs ? mix(facade, board.mul(0.3), signsHere) : facade;
  mat.colorNode = sel(isPattern, facade, sel(isRoof, roofColor, roofCodes ? sel(slopeRoof, slopeColor, wallFacade) : wallFacade));
  // how much of this point is glass: a curtain wall but for its mullions, louvres and coping; the
  // openings of other walls
  const patternOpen = patternGlass.mul(float(1).sub(patternMember)).mul(float(1).sub(patternFar.mul(0.5)));
  const openAmount = sel(isPattern, patternOpen, sel(isRoof.or(slopeRoof), float(0),
    sel(isCurtain, curtainGlass, signUse ? mix(glassNear, cover.mul(0.85), far).mul(float(1).sub(signboard.mask)) : mix(glassNear, cover.mul(0.85), far))));
  // glass roughness grows as panes shrink below a pixel, so the sun's glint spreads into a sheen rather
  // than sparkling on single pixels
  const glassRough = float(0.05).add(smoothstep(float(0.4), float(3), max(fx, fy)).mul(0.12));
  const solidRough = sel(isFactory, float(0.6), sel(isFins.or(isPattern).or(isSpire), float(0.4), float(0.88)));
  // (zinc and steel roofs: their sheen near, rougher with distance, where whole districts of zinc tops at a grazing
  // angle to the low sun added up to a washed-out near-white patch, Paris M9 orbit frames north-east of the Seine)
  const metalRough = mix(float(0.55), float(0.82), smoothstep(float(700), float(2500), positionWorld.sub(cameraPosition).length()));
  mat.roughnessNode = sel(isRoof.or(slopeRoof).and(isPattern.not()), sel(isFactory.and(blueSteel).or(zincRoof), metalRough, float(0.92)),
    mix(solidRough, glassRough, openAmount));
  mat.metalnessNode = float(0);
  // the sun glint off glass: the pane normals, and the coating's reflectance instead of plain 4 %
  const glassN = normalize(mix(N, Np, openAmount));
  mat.normalNode = normalize(cameraViewMatrix.mul(vec4(glassN, 0)).xyz);
  mat.specularColorNode = mix(vec3(1, 1, 1), coat.mul(f0.div(0.04)), openAmount);

  const reflectK = uniform(reflectStrength);       // the menu's reflections slider
  mat.userData.reflect = reflectK;
  mat.userData.tune = glassTune;
  // the reflection (two looks into the probe and the sky map, the ray's haze and sky grading) only where there is
  // glass: in a branch that solid wall, roofs and the stone between windows skip (at street level most of the
  // wall), its nodes a fresh copy built from the pane normal, height and roughness taken before it
  const glassReflection = branch ? Fn(() => {
    const k = (nearSoft ? coat.mul(fresnel).mul(openAmount).mul(reflectK).mul(float(1).sub(nearK.mul(nearSoft[3]))) : coat.mul(fresnel).mul(openAmount).mul(reflectK)).toVar();
    const NpV = Np.toVar(), yV = y.toVar(), roughV = lookupRough.toVar();
    const e = vec3(0).toVar();
    If(openAmount.greaterThan(0.0005), () => { e.assign(reflectionOf(NpV, yV, roughV).mul(k)); });
    return e;
  })() : nearSoft ? reflected.mul(coat).mul(fresnel).mul(openAmount).mul(reflectK).mul(float(1).sub(nearK.mul(nearSoft[3])))
    : reflected.mul(coat).mul(fresnel).mul(openAmount).mul(reflectK);
  mat.emissiveNode = (signs ? board.mul(signsHere.mul(0.55)).add(glassReflection.mul(float(1).sub(signsHere))) : glassReflection)
    .add(vec3(0.9, 0.9, 0.82).mul(ceilingLights.mul(float(1).sub(fresnel)).mul(0.12)));
  // the city's lights, in the material's lit copy (night.js), drawn only while they are on. Street light
  // falls on the wall's own colour (glass walls darker), not the full facade colour, which cost a second
  // evaluation of it
  // (at night brick and brownstone buildings are homes like residential towers)
  const lit = night && nightLights({ night, perStyle, style, is, isResi: isHome, isVillage, isFactory,
    isMall: nightKind('mall'), isPlain: nightKind('none').or(onWall.not()), isFlood: isFlood.or(isMon), isSpire, isFins, isCurtain, isPattern, isRoof: isRoof.or(slopeRoof), seed, height, y, s, runLen, col, row, F, cx, cy, fx, fy, wx, wy, xlo, xhi, ylo, yhi, ground, glassMask, cover,
    far, visX, visY, mull, blind, ceilingLights, fresnel, patternOpen, streetLight, albedo: wallColor.mul(sel(isCurtain, float(0.3), float(1))), roofColor, fwUV,
    // (night.corridors, Singapore M8: the corridor faces' lamps; only a city that asks and has a style with corridors)
    corr: night?.corridors && uses((d) => d.corridors) ? corrWall.and(onWall).and(isRoof.not()) : null, X,
    arc: night?.arcades && uses((d) => d.fiveFootWay) ? arcadeRow.and(onWall).and(isRoof.not()) : null,
    // (night.arcades.upper, Singapore M8 fix round 1: the closed shutters of the upper floors lit through their louvres)
    shut: night?.arcades?.upper && uses((d) => d.shophouseFront) ? shutRow.and(sgShut).and(onWall).and(isRoof.not()) : null });
  // billboards and LED screens (Times Square) blaze after dark: their art at screen brightness, on top of the
  // day's self-glow
  // (and the vertical signboards, lit from inside)
  // (facade.nightSigns { screens, boards }, Tokyo M8: those brightnesses, default 4 and 2.2)
  let litE = lit ? (signs ? lit.emissive.add(board.mul(signsHere).mul(nightSigns?.screens ?? 4)) : lit.emissive) : null;
  if (lit && signUse) litE = litE.add(signboard.colour.mul(signboard.mask).mul(nightSigns?.boards ?? 2.2));
  if (lit) night.withLights(mat, litE);
  // intermediate nodes, for trying things out from the browser console
  mat.userData.nodes = { glassWall, glassBody, visionBody, spandrelBody, frame, refuge, visX, visY, far, facade,
    patternColor, openAmount, wall, tint, fresnel, reflected, Np, ceilingLights, night: lit };
  return mat;
}

// ---------------------------------------------------------------- lights after dark
// linear colours of lamps: warm (2700 K), neutral (3500-4000 K), cool white (LED panels, fluorescent tubes)
const WARM = vec3(1, 0.6, 0.3), NEUTRAL = vec3(1, 0.8, 0.58), COOL = vec3(0.74, 0.84, 1);
// brightness of a lit room seen through clear glass, of a shopfront, of a sign (linear, before exposure)
const ROOM = 0.9, SHOP = 1.1, SIGN = 1.5;
// shop sign colours: red, blue, green, amber, white
const SIGNS = [vec3(1, 0.06, 0.04), vec3(0.08, 0.25, 1), vec3(0.1, 0.85, 0.3), vec3(1, 0.55, 0.05), vec3(0.9, 0.92, 1)];
// the share of the pixel footprint [t - w/2, t + w/2] inside [lo, hi]: a box-filtered band that stays
// right (its average) when it is thinner than a pixel
const boxBand = (t, lo, hi, w) => clamp(min(t.add(w.mul(0.5)), hi).sub(max(t.sub(w.mul(0.5)), lo)).div(max(w, 1e-4)), 0, 1);

// The emission of the city's lights on the facades, from the facade's own nodes (see createFacadeMaterial).
// Rooms are lit per zone: an office zone of a few bays, a flat's two windows, a village room's single one,
// each on or off by a hash against its floor's share; each floor's share scatters around its building's
// (offices' floors lit or dark as a whole), and each building's around the hour's share for its kind
// (night.js), with now and then an empty building. Zones narrower than a few pixels, and floors lower,
// are lit in groups whose shares scatter less as they grow, so a far tower glows at its average, its lit
// and dark floors banded as long as they show.
// 1 while the water's mirror is drawn (its camera stands below the sea), else 0
const inMirror = uniform(0).onRenderUpdate(({ camera }) => (camera.position.y < 0 ? 1 : 0));

function nightLights(n) {
  const { night: N, perStyle, style, is, isResi: isResi0, isVillage, isFactory, isMall, isPlain, isFlood: isFlood0, isSpire, isFins, isCurtain, isPattern, isRoof,
    seed, height, y, s, runLen, col, row, F, cx, cy, fx, fy, wx, wy, xlo, xhi, ylo, yhi, ground, glassMask, cover, far,
    visX, visY, mull, blind, ceilingLights, fresnel, patternOpen, streetLight, albedo, roofColor, fwUV, corr, X, arc, shut } = n;
  // (homes: the styles with night "home", styles.js; city.json night.homeStyles adds to them: Berlin's altbau, platte,
  // kma... fell to the civic schedule and its cool lamps, the riverside homes dark with cold-blue windows at 21:30;
  // Berlin M8 fix round)
  const isResi = isResi0;
  const WIN = N.windows;
  // (night.flood.at: circles inside which any building is floodlit, its windows dark: per vertex)
  const at = N.floodAt ?? [];
  const inAt = at.length ? varying(at.reduce((acc, [x, z, r]) => max(acc, f01(length(positionWorld.xz.sub(vec2(x, z))).lessThan(r))), float(0)))
    : float(0);
  const isFlood = at.length ? isFlood0.or(inAt.greaterThan(0.5)) : isFlood0;
  // spire-style parts under 300 m (domes, lead spires, crowns) floodlit too where the city says (night.flood.spires)
  const floodSpire = isSpire.and(height.lessThan(300)).and(N.floodSpires.greaterThan(0));
  const seedInt = floor(seed.mul(4093));
  const cellH = (a, b, salt) => hash(a.add(b.mul(613)).add(seedInt.mul(1543)).add(salt));
  // more values from one hash: its low digits, stretched by a prime (as multi() does)
  const more = (h, k) => fract(h.mul(k));
  const wallOnly = float(1).sub(f01(isRoof));

  // ---- what is the same all over a building is worked out per vertex (varyings), not per pixel: the
  // share of its rooms lit (the hour's for its kind, scattered per building, now and then an empty one),
  // its zone width, lamp colour mix, street light, sign and shop shares, crown and fins
  const kindShare = sel(isCurtain, N.office, sel(isResi, N.home, sel(isVillage, N.village, sel(isMall, N.mall,
    sel(isFactory, N.factory, sel(isPlain, float(0), N.civic))))));
  const vacant = sel(h1(seed.mul(47.3)).lessThan(0.06), float(0.15), float(1));          // unlet, unsold
  // lamp colours: the share of cool white rooms and of cool or neutral ones. Homes are mostly warm (2700-
  // 3500 K), villages' rooms often lit by cool tubes, offices cool white; each building leans one way or
  // the other (a whole estate fitted out alike)
  const coolK = sel(isCurtain, float(0.45), sel(isVillage, float(0.3), sel(isResi, float(0.15), float(0.4))))
    .mul(mix(float(0.3), float(1.7), h1(seed.mul(91.7))));
  const perB = varying(vec4(
    clamp(kindShare.mul(mix(float(0.35), float(1.45), h1(seed.mul(83.1)))).mul(vacant), 0, 1),
    // (night.windows.zone: the offices' zone in bays, London's lit floors broken by single dark bays, not blocks of seven)
    pick(style, perStyle((d) => (d.zone === 'office' ? WIN?.zone ?? 7 : d.zone), 2)),
    coolK,
    coolK.add(sel(isCurtain, float(0.5), float(0.33)))));
  const perB2 = varying(vec4(
    sel(isVillage, float(0.35), sel(isResi.or(isMall), float(0.12), float(0.06))),
    sel(isResi, float(0.25), float(0.5)),
    sel(isResi, float(0.45), float(1)),
    f01(isFins.and(height.greaterThan(300))).mul(sel(seed.greaterThan(0.8), float(0.6), float(0.25)))));
  const crownPick = h1(seed.mul(53.7));
  const perB3 = varying(sel(crownPick.lessThan(0.7), vec3(0.85, 0.9, 1), sel(crownPick.lessThan(0.85), vec3(0.25, 0.55, 1), vec3(1, 0.7, 0.3)))
    .mul(f01(height.greaterThan(120).and(h1(seed.mul(71.9)).lessThan(0.2)).and(isFins.not()))));
  const bShare = perB.x, zoneW = round(perB.y), tCool = perB.z, tNeutral = perB.w;

  // ---- the share of rooms lit per floor and per zone
  // Offices (and malls, civic buildings, factories) are worked in and lit a floor at a time: each floor
  // mostly lit or mostly dark, so they show lit bands; homes vary less from floor to floor.
  // Zones narrower than about 4 pixels or floors lower than about 3 are not drawn one by one (single pixels
  // on or off are what made towers a noisy mosaic): rooms are lit in groups of 2, 4, 8... zones and 1, 2,
  // 4... floors, at least that big on screen and blended between group sizes (as the glass's pane
  // variation), each group at its own share of lit rooms: its floors' share about the building's, and
  // the group's about that as the share of so many rooms would scatter (a binomial's spread, as a
  // uniform one of the same width); single zones on or off. The groups narrow the spread as they grow, so
  // a tower fades into a soft, floor-banded glow at its building's share.
  // (Paris M9: in branches, from copies of the inputs taken before them. Only where the wall shows a window
  // (or glass, or a patterned skin's glass): the stone between the windows skips the rooms altogether. Where
  // zones and floors are drawn one by one (up close: most of a street view), one hash for the floor and one
  // for the zone; the four groups' blend only where they are small on screen. Same result, bit for bit: the
  // near branch is the blend's own value at group size 1)
  const flats = isResi.or(isVillage);
  // (night.homes.far, Singapore M8 fix round 1: the lit windows' own fade, not the facade's grid fade)
  const HOM = N.homes;
  const farN = HOM?.far ? smoothstep(float(HOM.far[0]), float(HOM.far[1]), max(wx, wy)) : max(far, smoothstep(float(0.08), float(0.28), max(wx, wy)));
  const windowOpen = mix(glassMask.mul(float(1).sub(f01(ground))), cover.mul(0.85), farN);
  const roomsHere = isRoof.not().and(isPattern.or(isCurtain).or(windowOpen.greaterThan(0)));
  const roomsOf = (V, near) => {
    const curt = V.curt.greaterThan(0.5), patt = V.patt.greaterThan(0.5), fl = V.flats.greaterThan(0.5);
    const cellH = (a, b, salt) => hash(a.add(b.mul(613)).add(V.seedInt.mul(1543)).add(salt));
    const floorsLit = clamp(V.bShare.sub(0.06).div(0.82), 0, 1);
    const floorShare = (h) => sel(fl, clamp(V.bShare.mul(h.sub(0.5).mul(0.8).add(1)), 0, 1),
      mix(float(WIN?.darkFloor ?? 0.06), float(WIN?.litFloor ?? 0.88), f01(h.lessThan(floorsLit))));
    // zones shifted per floor (by the golden ratio's multiples: no hash needed), so their ends don't line up
    // into a grid
    const zone = floor(V.col.add(floor(fract(V.row.mul(0.618034).add(V.seed)).mul(V.zoneW))).div(V.zoneW));
    let lit, zoneH, floorH, blend, floorNear;
    if (near === 'far') {
      // groups of 16 zones and 8 floors or more (see roomsV): the building's own share, its mean
      lit = V.bShare;
      zoneH = floorH = float(0);
      blend = float(1);
      floorNear = float(0);
    } else if (near) {
      // zones and floors one by one (group size 1: Lx = Ly = 0)
      floorH = cellH(V.row, float(0), 11);
      zoneH = cellH(zone, V.row, 17);
      lit = f01(zoneH.lessThan(floorShare(floorH)));
      blend = float(0);
      floorNear = float(1);
    } else {
      // (the spread of a floor's share about the building's, as the width of a uniform one)
      // (night.homes.spread, Hong Kong M8: homes' groups scattered that share as much about their share: groups of rooms at
      // their own share made 2-3 km residential slopes a blotchy mosaic of tan blocks)
      const HSP = HOM?.spread;
      // (night.windows.spread, Hong Kong M8 fix round 1: offices' groups likewise: 1.5-2 km towers read as a blocky patchwork)
      const WSP = WIN?.spread;
      const floorSpread = sel(fl, V.bShare.mul(HSP != null ? 0.8 * HSP : 0.8), sqrt(floorsLit.mul(float(1).sub(floorsLit))).mul(WSP != null ? 2.84 * WSP : 2.84));
      const Lx = log2(max(V.fx.mul(4).div(V.zoneW), 1)), Ly = log2(max(V.fy.mul(3), 1));
      const lx = floor(Lx), ly = floor(Ly), ax = fract(Lx), ay = fract(Ly);
      const gx = exp2(lx), gy = exp2(ly);
      const floorGroup = (n, level) => {
        const h = cellH(floor(V.row.div(n)), float(0), level.mul(7919).add(11));
        return { h, p: mix(floorShare(h), clamp(V.bShare.add(h.sub(0.5).mul(floorSpread).div(sqrt(n))), 0, 1), f01(n.greaterThan(1.5))) };
      };
      const f0 = floorGroup(gy, ly), p0 = f0.p, p1 = floorGroup(gy.mul(2), ly.add(1)).p;
      // (groups of several floors are not shifted per floor, or their edges would jitter row by row)
      const zoneCol = floor(V.col.div(V.zoneW));
      const group = (p, nx, ny, lvx, lvy) => {
        const z = sel(ny.greaterThan(1.5), zoneCol, zone);
        const h = cellH(floor(z.div(nx)), floor(V.row.div(ny)), lvx.mul(7919).add(lvy.mul(3571)).add(17));
        const n = nx.mul(ny);
        const on = mix(f01(h.lessThan(p)), clamp(p.add(h.sub(0.5).mul(HSP != null || WSP != null ? sel(fl, float(3.46 * (HSP ?? 1)), float(3.46 * (WSP ?? 1))) : 3.46).mul(sqrt(p.mul(float(1).sub(p)).div(n)))), 0, 1),
          f01(n.greaterThan(1.5)));
        return { h, on };
      };
      const c00 = group(p0, gx, gy, lx, ly), c10 = group(p0, gx.mul(2), gy, lx.add(1), ly);
      const c01 = group(p1, gx, gy.mul(2), lx, ly.add(1)), c11 = group(p1, gx.mul(2), gy.mul(2), lx.add(1), ly.add(1));
      // (towards the far branch's groups, their mean: no step where it takes over)
      lit = mix(mix(mix(c00.on, c10.on, ax), mix(c01.on, c11.on, ax), ay), V.bShare, smoothstep(float(3), float(4), min(Lx, Ly.add(1))));
      // a zone's own lamp, brightness and curtains while zones are drawn one by one; their mean beyond
      zoneH = c00.h;
      floorH = f0.h;
      blend = clamp(max(Lx, Ly), 0, 1);
      floorNear = float(1).sub(clamp(Ly, 0, 1));
    }
    // rooms "off" are rarely black: corridor and emergency lights, a lit room further in (offices more)
    const glowK = mix(sel(curt, float(0.06), float(0.02)), float(1), lit);

    // ---- the lamps: colour (per room in homes, per floor elsewhere: a tenant's fit-out), brightness,
    // curtains; averaged like the zones
    const ct = more(sel(fl, zoneH, floorH), 211);
    // (offices' neutral is the whiter one of office LED panels)
    const neutral = sel(curt, WIN?.neutral ? vec3(...WIN.neutral) : vec3(1, 0.9, 0.76), NEUTRAL);
    const cool = WIN?.cool ? sel(curt, vec3(...WIN.cool), COOL) : COOL;
    // (night.windows: offices lit by cool and neutral panels only, about 4,000 K, no warm floors)
    const warm = WIN ? sel(curt, neutral, WARM) : WARM;
    const lamp = mix(mix(cool, neutral, f01(ct.greaterThan(V.tCool))), warm, f01(ct.greaterThan(V.tNeutral)));
    const lampAvg = cool.mul(V.tCool).add(neutral.mul(V.tNeutral.sub(V.tCool))).add(warm.mul(float(1).sub(V.tNeutral)));
    // curtains drawn in some homes: dimmer and warmer, the light through beige cloth
    const curtained = f01(more(zoneH, 389).lessThan(sel(curt, float(0), float(HOM?.curtains ?? 0.3))));
    // how bright: offices' ceiling panels fairly even; homes a few bright rooms and many dim ones (a lamp, a
    // TV, a light further in); their means (0.9, and 0.65 less the curtains' dimming: 0.53)
    const bh = more(zoneH, 1409);
    // (night.windows.even: an office floor's panels alike, a little brighter or dimmer per floor, not per zone)
    // (night.windows.vary: and each zone of a floor ±vary/2 about it, a little unevenness in a lit floor: Berlin M8 fix round)
    const evenK = WIN?.vary ? mix(float(0.8), float(1), more(floorH, 1409)).mul(mix(float(1 - WIN.vary / 2), float(1 + WIN.vary / 2), more(zoneH, 733))) : mix(float(0.8), float(1), more(floorH, 1409));
    // (night.homes.room: homes' lit rooms evenly between lo and hi: no dim mid-tone rooms)
    const roomK = sel(curt, WIN?.even ? evenK : mix(float(0.6), float(1.2), bh), HOM?.room ? mix(float(HOM.room[0]), float(HOM.room[1]), bh) : mix(float(0.22), float(1.5), bh.mul(bh)))
      .mul(mix(float(1), float(0.4), curtained));
    const roomAvg = sel(curt, float(0.9), float(HOM?.room ? (HOM.room[0] + HOM.room[1]) / 2 * (1 - 0.6 * (HOM.curtains ?? 0.3)) : 0.53));
    // (averaged, less saturated: resolved, warm windows clip towards yellow white, and a saturated orange
    // mean at a low brightness reads as a brown veil over the blocks)
    const avgCol = mix(lampAvg, vec3(dot(lampAvg, vec3(0.2126, 0.7152, 0.0722))), 0.35);
    const roomCol = mix(lamp.mul(roomK).mul(mix(vec3(1, 1, 1), vec3(1, 0.78, 0.58), curtained)), avgCol.mul(roomAvg), blend);

    // ---- ordinary windows (not the ground floor's shopfronts): brighter towards the ceiling. Lit, a window
    // under a couple of pixels wide stripes the wall as the pixel grid beats with the window grid, so the
    // lights give way to their mean sooner than the wall does (farN: from cells of about 9 pixels to 3)
    const vy = clamp(V.cy.sub(V.ylo).div(max(V.yhi.sub(V.ylo), 0.01)), 0, 1);
    // near, in homes and villages: the sliding window's meeting stiles in the middle, curtains drawn part way
    // in from the sides (dimmer, warmer), the ceiling lamp's hot spot; far away their mean
    const flatsK = V.flats;
    const ow = max(V.xhi.sub(V.xlo), 0.01);
    const u = clamp(V.cx.sub(V.xlo).div(ow), 0, 1);
    const drape = more(zoneH, 5807).mul(0.4).mul(flatsK);
    const drawn = float(1).sub(band(u, drape, float(1).sub(drape), V.wx.div(ow)));
    const stiles = band(u, float(0.48), float(0.52), V.wx.div(ow)).mul(flatsK);
    const hot = exp(u.sub(0.5).mul(u.sub(0.5)).add(vy.sub(0.85).mul(vy.sub(0.85))).mul(-10)).mul(0.4).add(0.85);
    const inside = mix(vec3(1, 1, 1), vec3(0.5, 0.38, 0.27), drawn).mul(hot).mul(float(1).sub(stiles.mul(0.85)));
    const windows = V.windowOpen.mul(mix(mix(float(0.7), float(1.15), vy), float(0.93), V.farN));
    const windowLook = mix(inside, vec3(0.9, 0.88, 0.86), V.farN);
    // curtain walls: the office seen through the vision glass (what the coating lets through), ceiling bright,
    // desks darker, a lowered blind glowing softly; the ceiling lights line where resolved
    const officeGrad = mix(float(0.85), mix(float(0.5), float(1.2), vy), floorNear);
    // (night.windows.even: no blinds' variation inside the lit panes: London's lit floors read mottled)
    const vision = V.visX.mul(V.visY).mul(float(1).sub(V.fresnel)).mul(officeGrad).mul(WIN?.even ? float(0.85) : mix(float(1), float(0.65), V.blind))
      .add(V.ceilingLights.mul(1.5));
    // averaged, the rooms are dimmed a little: seen resolved, lit windows clip to near white in the tone
    // mapping, so their share of a pixel looks darker than their linear mean would
    // (windows still resolved but lit at a group's share hardly: they keep their punch. Not at all in the
    // water's mirror, drawn by a camera below the sea: its image is blurred and smeared into streaks, which
    // want the true mean, or the lit skyline across the bay mirrors as a dull sheet)
    const clip = mix(float(1), float(0.32), max(blend.mul(0.25), V.farN).mul(float(1).sub(inMirror)));
    // (night.windows.office: the offices' lit rooms times that: Berlin's lit floors outshone the landmarks)
    let out = sel(patt, vec3(V.patternOpen.mul(0.7)), sel(curt, vec3(WIN?.office ? vision.mul(WIN.office) : vision), windowLook.mul(windows))).mul(glowK).mul(roomCol).mul(ROOM)
      .mul(clip);
    // (night.homes.glitter { dot, k }, Hong Kong M8 fix round 1, default none: homes' windows too small to draw (farN) as
    // a glitter of whole lit windows, not their mean: per pixel a window cell (col, row) lit at `dot` of a full window's
    // light with the chance that keeps the mean (the share lit x the open share / dot), its own lamp and brightness, times
    // k; the clip's dimming left out (the dots clip white as real ones do). Not in the water's mirror (its streaks want
    // the mean). Kowloon at 2-4 km read as tan blocks: the lit windows averaged into a cardboard tone)
    if (near !== true && HOM?.glitter) {
      const G = { dot: 0.9, k: 1, ...HOM.glitter };
      const gh = cellH(floor(V.col), floor(V.row), 29);
      const q = V.bShare.mul(V.windowOpen).mul(0.93 / G.dot);
      const gct = more(gh, 211);
      const glamp = mix(mix(cool, neutral, f01(gct.greaterThan(V.tCool))), warm, f01(gct.greaterThan(V.tNeutral)));
      const groom = HOM.room ? mix(float(HOM.room[0]), float(HOM.room[1]), more(gh, 1409)) : mix(float(0.6), float(1.2), more(gh, 1409));
      const glit = vec3(0.9, 0.88, 0.86).mul(glamp).mul(groom).mul(f01(more(gh, 7307).lessThan(q))).mul(G.dot * G.k * ROOM);
      out = sel(fl.and(patt.not()).and(curt.not()), mix(out, glit, V.farN.mul(float(1).sub(inMirror))), out);
    }
    // (night.windows.max: a lit room no brighter than that, linear: below the tone mapping's white)
    return WIN?.max ? out.min(WIN.max) : out;
  };
  const roomsV = Fn(() => {
    const V = Object.fromEntries(Object.entries({ curt: f01(isCurtain), patt: f01(isPattern), flats: f01(flats), seedInt, seed,
      bShare, zoneW, tCool, tNeutral, col, row, fx, fy, cx, cy, xlo, xhi, ylo, yhi, wx, windowOpen, farN,
      visX, visY, fresnel, blind, ceilingLights, patternOpen }).map(([k, n]) => [k, n.toVar()]));
    const out = vec3(0).toVar();
    // (up close: zones at least 4 pixels wide and floors 3 high, Lx = Ly = 0)
    const near = V.fx.mul(4).div(V.zoneW).lessThanEqual(1).and(V.fy.mul(3).lessThanEqual(1));
    // (far: zones in groups of 16 and floors of 8 or more, Lx >= 4 and Ly >= 3, where a group's spread about the
    // building's share is a few per cent and the six hashes of the blend buy nothing: most of an overview)
    const Lx = log2(max(V.fx.mul(4).div(V.zoneW), 1)), Ly = log2(max(V.fy.mul(3), 1));
    const farOnly = min(Lx, Ly.add(1)).greaterThanEqual(4);
    If(roomsHere.and(near), () => { out.assign(roomsOf(V, true)); })
      .ElseIf(roomsHere.and(farOnly), () => { out.assign(roomsOf(V, 'far')); })
      .ElseIf(roomsHere, () => { out.assign(roomsOf(V, false)); });
    return out;
  })();
  // (times wallOnly, 1 wherever rooms are drawn: it builds wallOnly here, at the top level, for the branches below)
  const rooms = (at.length ? roomsV.mul(float(1).sub(inAt)) : roomsV).mul(wallOnly);

  // ---- shopfronts and their signs on the ground floors of homes, villages and podiums: per shop (a bay in
  // villages, two elsewhere) lit or not by the shops' hour, most in cool white, a sign band above in one of
  // the sign colours. Far away the ground floor is a sliver: its box-filtered share of the pixel, lit at
  // the average
  const hasShops = f01(isResi.or(isVillage).or(isMall));
  // (Paris M9: functions, so the near branch and the far one each build nodes of their own: the shops one by one
  // only where the ground floor is resolved, far < 1; beyond, their box-filtered mean)
  // (apartment towers have fewer shops below them than villages and podiums: lobbies, bike sheds)
  const shopShareOf = () => N.shops.mul(perB2.z);
  const shopNearOf = () => {
    const shop = floor(col.div(sel(isVillage, float(1), float(2))));
    const shopH = cellH(shop, float(0), 37);
    const shopOn = f01(shopH.lessThan(shopShareOf()));
    // mostly warm and neutral white, some cool (convenience stores, phone shops), from dim (a noodle bar, a
    // hardware shop) to bright; brighter under the ceiling, the goods and counters below darker
    const st = more(shopH, 97);
    const shopCol = mix(mix(WARM, NEUTRAL, f01(st.greaterThan(0.3))), COOL, f01(st.greaterThan(0.75)))
      .mul(mix(float(0.3), float(1.2), more(shopH, 5807))).mul(smoothstep(float(0.05), float(0.8), cy).mul(0.7).add(0.35));
    const signPick = floor(more(shopH, 389).mul(5));
    let signCol = SIGNS[0];
    for (let i = 1; i < SIGNS.length; i++) signCol = sel(signPick.greaterThan(i - 0.5), SIGNS[i], signCol);
    const signOn = f01(more(shopH, 1409).lessThan(perB2.y));
    // (signs of their own widths, not one unbroken band along the street)
    const signIn = mix(float(0.06), float(0.35), more(shopH, 23201));
    const signMask = band(cy, float(0.87), float(0.97), wy).mul(band(cx, signIn, float(1).sub(signIn), wx));
    return glassMask.mul(shopCol).mul(SHOP).add(signMask.mul(signOn).mul(signCol).mul(SIGN)).mul(shopOn)
      .mul(f01(ground));
  };
  const shopFarOf = () => vec3(0.94, 0.75, 0.6).mul(shopShareOf()).mul(boxBand(F, float(0), float(1), fy))
    .mul(float(0.3 * SHOP).add(perB2.y.mul(0.05 * SIGN)));
  // (night.arcades.shops: the shop windows' light times that on a five-foot way's row (Singapore M8 fix round 1: flat
  // glowing panels under the arcade, the soffit and piers dark beside them))
  const arcShops = arc && N.arcades.shops != null ? sel(arc, float(N.arcades.shops), float(1)) : null;
  const shopsOf = (near) => {
    const o = (near ? mix(shopNearOf(), shopFarOf(), far) : shopFarOf()).mul(hasShops).mul(wallOnly);
    return arcShops ? o.mul(arcShops) : o;
  };

  // ---- street light on the lower walls: lamps every 25 m along the street and the shops' spill, fading
  // up the wall; strongest in the villages' narrow lanes
  const fs = max(fwidth(s), 1e-3);
  const pools = mix(cos(s.mul(Math.PI * 2 / 25)).mul(0.45).add(0.55), float(0.55), smoothstep(float(5), float(12), fs));
  // (a city with its real lamps (lamps.js streetLight): their light 3 m out from the wall, so the walls of courtyards
  // and light wells, which no lamp lights, stay dark)
  const lampLight = streetLight ? streetLight(positionWorld.add(normalWorldGeometry.mul(3))).mul(1.4) : float(1);
  const wash = albedo.mul(vec3(1, 0.72, 0.48)).mul(pools).mul(lampLight).mul(exp(y.mul(-1 / 6))).mul(perB2.x).mul(wallOnly);

  // ---- feature lighting (from dusk to 23 h): the stainless fins of the supertalls lit white from top to
  // bottom, brightening towards the top (China Resources' 56 ribs most), with a glowing crown; a lit band
  // round the top of some other towers over 120 m
  const fyw = max(fwidth(y), 1e-3);
  const up = clamp(y.div(height), 0, 1);
  const ribs = mull.mul(perB2.w).mul(up.mul(up).mul(0.8).add(0.4));
  const crownTop = boxBand(y, height.mul(0.93), height.sub(1), fyw).mul(f01(perB2.w.greaterThan(0))).mul(visX).mul(0.4);
  const crownBand = boxBand(y, height.sub(4.5), height.sub(1.2), fyw);
  const feature = vec3(0.85, 0.92, 1).mul(ribs.add(crownTop)).add(perB3.mul(crownBand)).mul(N.feature).mul(wallOnly);

  // ---- red obstruction lights at the top corners of buildings over 250 m (lower ones' are too small to see), kept about two pixels across
  // however far (a point light's glare, which a sub-pixel dot would lose)
  const r = clamp(max(max(fwidth(y), 1e-3), fwidth(s)), 0.7, 4);  // (at most 4 m: seen from above, walls are steep)
  const toCorner = vec2(min(s, runLen.sub(s)), y.sub(height).add(r).add(0.4));
  const beacon = float(1).sub(smoothstep(r.mul(0.5), r, length(toCorner))).mul(f01(height.greaterThan(250))).mul(wallOnly);
  const obstruction = vec3(1, 0.01, 0.005).mul(beacon);

  // ---- roofs: once twilight has gone, the city's glow on the haze above lights them faintly, a neutral
  // warm grey (the hemisphere light alone left them a flat navy under the moon; more, and every roof in an
  // aerial view turned into a brown veil)
  const skyBounce = roofColor.mul(vec3(0.012, 0.011, 0.0095)).mul(N.cityGlow).mul(f01(isRoof));
  // and the odd lamp on them, over a stair or lift door, on a plant room: small warm pools of different
  // brightness on a jittered 30 m grid, one cell in thirty (more read as a pattern of dots), their mean once
  // they shrink to a few pixels; in a branch, roofs only (fwUV: metres per pixel on roofs)
  const roofNear = float(1).sub(smoothstep(float(0.5), float(1.5), fwUV));
  const roofLampsMean = () => roofColor.mul(WARM).mul(Math.PI * 2.5 * 0.8 / 30 / 900).mul(2.5);
  const roofLamps = () => {
    const q = vec2(positionWorld.x, positionWorld.z).div(30);
    const h = hash2(floor(q.x), floor(q.y));
    const d = fract(q).sub(vec2(more(h, 97), more(h, 389)).mul(0.8).add(0.1)).mul(30);
    const pool = exp(dot(d, d).div(-2.5)).mul(f01(h.lessThan(1 / 30))).mul(more(h, 1409).add(0.3));
    return roofColor.mul(WARM).mul(mix(float(Math.PI * 2.5 * 0.8 / 30 / 900), pool, roofNear)).mul(2.5);
  };

  // Rooms light every wall; the rest only parts of some, so each is added in a branch that whole buildings
  // or bands of them skip together (the ground floor, the lowest 30 m, the tops): about a quarter of the
  // lit shader's cost off most pixels. Each branch's nodes are its own (a node shared between branches, or
  // first built inside one, would be declared in that branch's scope only).
  // ---- floodlit monuments (the floodlit style): their own colour washed by floodlights all night, from low
  // lamps to the south-south-east with a softer fill all round (so drapery keeps its relief), brighter towards
  // the top; the style parameter (the landmark's variant) sets the strength, 0.98 or more glows (a flame)
  // Floodlight is light: it falls on the facade's own colour (diffuseColor: arcades, columns, windows and joints
  // as by day, not the wall's flat tint), strongest low down near the lamps and fading up the walls, from lamps to
  // the south-south-east with a softer fill all round (so relief keeps its shading), plus a little ambient spill.
  // Roofs, domes and spires (floodSpire) at a lower strength and a cooler tint, so a green copper dome stays green.
  // The style parameter (the landmark's variant) sets the strength, 0.98 or more glows (a flame)
  const flame = f01(seed.greaterThan(0.98));
  const yRel = clamp(y.div(max(height, 1)), 0, 1);
  const floodK = exp(yRel.mul(-1.8)).mul(0.8).add(0.3);                        // 1.1 at the foot, 0.43 at the top
  // (night.flood.fallM: the light falls off over that many metres of height instead of the part's own height, from a
  // bright plinth to about half at a 20 m cornice: Berlin M8 fix round, the Reichstag flat cream on every face)
  // (night.flood.ground: measured from that scene height instead of the part's foot: a figure standing on a roof (a
  // tower's top, a sphere at 200 m) is lit as high up as it is, not as a plinth)
  const yF = N.floodGround != null ? max(positionWorld.y.sub(N.floodGround), 0) : y;
  const floodK2 = N.floodFallM ? exp(yF.div(-N.floodFallM)).mul(0.9).add(0.2) : floodK;
  const key = clamp(dot(normalize(normalWorldGeometry), normalize(vec3(0.45, 0.25, 0.85))), 0, 1);
  const onTop = smoothstep(float(0.2), float(0.6), normalWorldGeometry.y);
  const topK = sel(isSpire, N.floodSpires, float(1)).mul(mix(float(1), float(N.floodRoof ?? 0.45), onTop));
  const tint = mix(N.floodTint, N.floodRoofTint, max(onTop, f01(isSpire)));
  // (the city's flood light, night.js: its tint on the stone, a gain and the least strength; a lattice tower's
  // solid members over 300 m, the Eiffel Tower's, glow in its gold from the lamps inside it instead)
  const goldTower = f01(height.greaterThan(300).and(N.goldTower.x.greaterThan(0)));
  const dc = diffuseColor.rgb;
  const floodLight = dc.mul(tint).mul(floodK2.mul(key.mul(0.6).add(0.4)).mul(max(seed.mul(0.7), N.floodMin)).mul(N.floodGain).mul(topK).add(0.05));
  const dcN = mix(vec3(1, 1, 1), dc.div(max(dot(dc, vec3(0.2126, 0.7152, 0.0722)), 0.02)), 0.3);   // (the paint's hue, not its darkness)
  let goldLight = (N.goldLattice?.colour ? N.goldLattice.colour(positionWorld.y) : N.goldTower).mul(dcN).mul(key.mul(0.5).add(0.6)).mul(1.1);
  // (night.goldLattice: the chords, arches, friezes and decks by the lamp stages' light as the lattice is, lattice.js)
  if (N.goldLattice) goldLight = goldLight.mul(N.goldLattice.stage(positionWorld.y)).mul(N.goldLattice.solid);
  // (night.flood.low: parts lower than that many metres get no floodlight: the East Side Gallery's 3.6 m wall glowed in its
  // murals' full day colours; Berlin M8 fix round)
  const floodOn = N.floodLow ? f01(isFlood.or(floodSpire).and(height.greaterThan(N.floodLow))) : f01(isFlood.or(floodSpire));
  const flood = mix(mix(floodLight, vec3(1, 0.62, 0.22).mul(4), flame), goldLight, goldTower).mul(floodOn);

  // lit crowns (built here, outside the branch that adds them: see above)
  const crownH = min(float(110), height.mul(0.25));
  const crownUp = clamp(y.sub(height.sub(crownH)).div(crownH), 0, 1);
  // (from nothing at the band's foot, brightest at the top, the windows left dark: starting at half strength
  // and washing over the windows it read as a cream sleeve with a hard lower edge)
  const crownLit = vec3(0.34, 0.3, 0.24).mul(crownUp.mul(crownUp).mul(0.9).add(crownUp.mul(0.15)))
    .mul(float(1).sub(glassMask.mul(0.85))).mul(wallOnly);

  // ---- an open corridor face's lamps (night.corridors, Singapore M8: HDB slabs' rows of lit corridors, on all night):
  // per floor the corridor behind the parapet (its band as corridorAccess draws it, F 0.37-0.95), brightest under the
  // ceiling, a lamp every `every` bays (a pool along the corridor), one in 1/dead out; each band, the gradient and the
  // pools box-filtered to their mean once a floor or a lamp's spacing is a few pixels (no stripes beating with the
  // pixel grid); each block's lamps warm or cool white
  const corridorLights = () => {
    const C = N.corridors;
    const ft = fract(F);
    const recess = stripe(F, float(0.37), float(0.95), fy);
    const t = clamp(ft.sub(0.37).div(0.58), 0, 1);
    const grad = mix(t.mul(t).mul(0.75).add(0.25), float(0.5), smoothstep(float(0.15), float(0.4), fy));
    const q = X.div(C.every);
    const fq = max(fwidth(q), 1e-3);
    const pool = mix(cos(q.mul(Math.PI * 2)).mul(0.45).add(0.55), float(0.55), smoothstep(float(0.2), float(0.5), fq));
    const out = mix(f01(cellH(floor(q), floor(F), 59).lessThan(C.dead)).mul(0.85), float(C.dead * 0.85), smoothstep(float(0.2), float(0.5), max(fq, fy)));
    const colour = mix(vec3(...C.colour), vec3(...C.cool), f01(h1(seed.mul(67.3)).lessThan(C.coolShare)));
    return colour.mul(C.k).mul(recess).mul(grad).mul(pool).mul(float(1).sub(out)).mul(wallOnly);
  };

  // ---- a five-foot way after dark (night.arcades, Singapore M8): per shop between the piers (as fiveFootWay draws them)
  // the shop front's doorway and the walkway's soffit lit, warm or neutral, by the shops' hour; their mean when small
  const arcadeLights = () => {
    const A = N.arcades;
    const n = max(float(1), round(runLen.div(A.unit)));
    const unit = runLen.div(n);
    const u = s.div(unit), fu = fs.div(unit), shop = floor(u);
    const open = float(1).sub(stripe(u, float(0), float(0.55).div(unit), fu));
    const h = cellH(shop, float(0), 71);
    const small = smoothstep(float(0.2), float(0.5), max(fu, fy));
    const on = mix(f01(h.lessThan(N.shops)), N.shops, small);
    const colour = mix(WARM, NEUTRAL, f01(more(h, 97).greaterThan(0.45))).mul(mix(float(0.55), float(1.1), mix(more(h, 389), float(0.8), small)));
    const door = stripe(u, float(0.24), float(0.8), fu).mul(boxBand(cy, float(0.035), float(0.6), fy));
    // (Singapore M8 fix round 1, all optional: door, soffit, spill, the shop front's, the soffit's and the walkway's even
    // spill's shares (0.9, 0.45, 0.08); gradient, the soffit brightest under the ceiling's lamps, falling to that share at
    // its foot (none: even): the doorways had read as flat glowing panels in a dark row)
    const soffit = A.gradient != null ? boxBand(cy, float(0.5), float(0.78), fy).mul(mix(float(A.gradient), float(1), smoothstep(float(0.5), float(0.78), cy)))
      : boxBand(cy, float(0.5), float(0.78), fy);
    const spill = boxBand(cy, float(0), float(0.78), fy);
    return colour.mul(door.mul(A.door ?? 0.9).add(soffit.mul(A.soffit ?? 0.45)).add(spill.mul(A.spill ?? 0.08))).mul(on).mul(open).mul(A.k).mul(wallOnly);
  };
  // (night.arcades.upper: [share, k]: that share of the home share of the upper floors' closed shutters glow warm through
  // their louvres, k their brightness; their mean far off)
  const shutterLights = () => {
    const [share, k] = N.arcades.upper;
    const win = band(cx, xlo, xhi, wx).mul(band(cy, ylo, yhi, wy));
    const h = cellH(col, row, 83);
    const small = smoothstep(float(0.2), float(0.5), max(wx, wy));
    const on = mix(f01(h.lessThan(N.home.mul(share))), N.home.mul(share), small);
    // (warmer or dimmer per window: a lamp further in; no derivatives in the branch)
    return WARM.mul(win).mul(mix(more(h, 389).mul(0.6).add(0.5), float(0.8), small)).mul(on).mul(k).mul(wallOnly);
  };

  // ---- (night.boards, Hong Kong M8 fix round 1, default none) rooftop sign boards: on a `share` of the towers over minH m
  // (not homes), the wall facing `face` [x, z] (scene m: the harbour) carries a lit board under its top, from `top[0]` to
  // `top[1]` m below it, over the middle `span` of the wall, in one of `colours` (linear) times k: letters as blocks of a
  // 3 x 5 grid per glyph (glyph `glyph` x the board's height wide), their mean once a glyph cell is under ~2 pixels.
  // Wan Chai's and Central's waterfront towers wear red, blue, white and green company boards that the harbour mirrors
  const B = N.boards;
  // (within [x, z, r]: only towers inside that circle, the harbour's two fronts)
  const boardOn = B ? varying(f01(height.greaterThan(B.minH ?? 90).and(isResi.not()).and(isVillage.not()).and(h1(seed.mul(61.3)).lessThan(B.share ?? 0.3))
    .and(B.within ? length(positionWorld.xz.sub(vec2(B.within[0], B.within[1]))).lessThan(B.within[2]) : bool(true)))) : null;
  const boards = () => {
    const [t0, t1] = B.top ?? [10, 3];
    const bh = t0 - t1;
    const toFace = normalize(vec2(...B.face).sub(positionWorld.xz));
    const facing = smoothstep(float(0.55), float(0.75), dot(normalize(normalWorldGeometry.xz.add(vec2(1e-4, 0))), toFace));
    const span = B.span ?? 0.7;
    const sr = s.div(max(runLen, 1));
    const inX = band(sr, float((1 - span) / 2), float((1 + span) / 2), fs.div(max(runLen, 1)));
    const inY = boxBand(y, height.sub(t0), height.sub(t1), fyw);
    const cols = B.colours ?? [[1, 0.08, 0.06], [0.2, 0.45, 1], [0.9, 0.95, 1], [0.1, 1, 0.35]];
    const pickC = h1(seed.mul(37.9));
    let colour = vec3(...cols[0]);
    for (let i = 1; i < cols.length; i++) colour = sel(pickC.greaterThan(i / cols.length), vec3(...cols[i]), colour);
    // glyphs: 3 x 5 blocks (a 4 x 6 cell with a gap), a block lit by a hash
    const gw = bh * (B.glyph ?? 0.7);
    const gx = s.div(gw / 4), gy = y.sub(height.sub(t0)).div(bh / 6);
    const blk = hash(floor(gx).add(floor(gy).mul(57)).add(floor(seed.mul(4093)).mul(131)));
    const inCell = f01(fract(gx.div(4)).lessThan(0.75)).mul(f01(gy.greaterThan(0.5).and(gy.lessThan(5.5))));
    const near = f01(blk.lessThan(0.62)).mul(inCell);
    const fine = smoothstep(float(0.5), float(1.2), max(fs.div(gw / 4), fyw.div(bh / 6)));
    return colour.mul(mix(near, float(0.62 * 0.75 * 5 / 6), fine)).mul(inX).mul(inY).mul(facing).mul(B.k ?? 2).mul(N.feature).mul(wallOnly);
  };

  const emissive = Fn(() => {
    const e = rooms.add(skyBounce).toVar();
    if (B) If(boardOn.greaterThan(0.5).and(y.greaterThan(height.sub((B.top ?? [10, 3])[0] + 1).sub(fyw))), () => { e.addAssign(boards()); });
    If(isFlood.or(floodSpire), () => { e.addAssign(flood); });
    // (Paris M9: their mean where they are under a few pixels: most roofs of an overview)
    // (night.roofLamps: their strength, 0 none: London, where they read as light pools on every roof)
    const RL = N.roofLamps ?? 1;
    if (RL > 0) If(isRoof.and(roofNear.greaterThan(0)), () => { e.addAssign(roofLamps().mul(RL)); }).ElseIf(isRoof, () => { e.addAssign(roofLampsMean().mul(RL)); });
    If(hasShops.greaterThan(0.5).and(F.sub(fy.mul(0.5)).lessThan(1)), () => {
      If(far.lessThan(1), () => { e.addAssign(shopsOf(true)); }).Else(() => { e.addAssign(shopsOf(false)); });
    });
    If(y.lessThan(30), () => { e.addAssign(wash); });
    if (corr) If(corr, () => { e.addAssign(corridorLights()); });
    if (arc) If(arc, () => { e.addAssign(arcadeLights()); });
    if (shut) If(shut, () => { e.addAssign(shutterLights()); });
    If(N.feature.greaterThan(0).and(perB2.w.greaterThan(0).or(perB3.x.greaterThan(0).and(y.greaterThan(height.sub(6).sub(fyw))))),
      () => { e.addAssign(feature); });
    If(height.greaterThan(250).and(y.greaterThan(height.sub(10))).and(min(s, runLen.sub(s)).lessThan(10)), () => { e.addAssign(obstruction); });
    // lit crowns: the tallest towers (over 240 m: the Empire State, the Chrysler, 1 WTC's parapet) wash their
    // top 110 m with floodlights, warm white, brightest at the top, on their walls, not through the glass
    // (the top quarter, at most 110 m: a tower's height runs to its tip, the Empire State's to its antenna)
    // no light brighter than a lamp: a runaway term (a window band divided by a sub-pixel width) bloomed into
    // orbs across the view; NaN (from any such division) goes dark rather than white
    return select(e.x.equal(e.x).and(e.y.equal(e.y)).and(e.z.equal(e.z)), e.clamp(0, 6), vec3(0));
  })();
  // (the crowns outside the branches: added last, masked, so no node of theirs is scoped to a branch)
  // (the towers named as floodlit, the 'crowned' style (stone by day; landmark_facades.csv): New York's
  // Empire State, Chrysler, 40 Wall Street, Woolworth, 70 Pine, 30 Rockefeller Plaza; a rule on stone and height
  // also lit 432 Park, 220 Central Park South and the MetLife slab, which are dark. And a metal crown cut from a
  // landmark's body (tiles.py crown@: the Chrysler's stainless arches, its top at 282 m) over 240 m whose top is
  // under 300 m: the masts and antennas above that, the Empire State's and 1 WTC's, stay dark)
  // (a tower made of OSM parts has a height per part: only its tall parts, over 150 m, carry the crown, or every
  // setback of the Empire State glowed at its own top)
  const crownMask = f01(y.greaterThan(height.sub(crownH))
    .and(is('crowned').and(height.greaterThan(150)).or(is('spire').and(height.greaterThan(240)).and(height.lessThan(300)))));
  // a small glass-and-steel lattice (the Louvre's pyramid, under 30 m) glows from the lit hall inside, neutral
  // white brightest low down; the steel style's towers stay as they are (masked, outside the branches)
  const glassHall = vec3(0.8, 0.86, 0.95).mul(float(1).sub(clamp(y.div(max(height, 1)), 0, 1).mul(0.5))).mul(0.55)
    .mul(f01(is('lattice').and(height.lessThan(30))));
  // feature lighting of named landmarks (night.glows): per pixel (circle, height band, ramp; a tower's walls are
  // single tall quads, and per-vertex values interpolated across a triangle half in a circle drew diagonal streaks)
  let glowLit = vec3(0, 0, 0), glowDark = float(0);
  // (on: 'lattice': the glow is the lattice's glazing or fabric's own (lattice.js), not the buildings' round it: Berlin M8
  // fix round, the Sony Center's tent lit the forum's roofs and walls lavender while the tent itself stayed dark)
  const bGlows = (N.glows ?? []).filter((g) => (g.on ?? 'buildings') !== 'lattice');
  // (London M8 fix round, all optional: shell [r0, r1], only what lies that far from the point hub [x, y, z] (a
  // wheel's rim, its capsules, its spokes: not every building inside the circle); plane [nx, nz, w], only within w
  // of the vertical plane through `at` with that normal (the wheel's own plane); flood, the light falls on the
  // surface's own colour from low lamps (a floodlit dome: its relief and stone kept) instead of a flat glow;
  // bands [storey, share], lit storeys through glazing, each on or off by a hash (a tower's lit floors);
  // radial, fade, grid: night.js glowMask; dark: the buildings' own lights (windows, floodlight) off where it glows)
  // (glowTerm: one glow's light at this pixel from pw, nw, dc (a branch's copies of the world position, the geometry's world
  // normal and the albedo), the same as the loop below that the default path keeps as it was)
  const glowTerm = (g, pw, nw, dc) => {
    const gy = pw.y, [y0] = g.y;
    let mask = glowMask(g, nw, dc, pw);
    if (g.shell) {
      const d = length(pw.sub(vec3(...(g.hub ?? [g.at[0], (g.y[0] + g.y[1]) / 2, g.at[1]]))));
      mask = mask.mul(smoothstep(float(g.shell[0] - 0.2), float(g.shell[0] + 0.2), d)).mul(float(1).sub(smoothstep(float(g.shell[1] - 0.2), float(g.shell[1] + 0.2), d)));
    }
    if (g.plane) {
      const off = abs(dot(pw.xz.sub(vec2(g.at[0], g.at[1])), vec2(g.plane[0], g.plane[1])));
      mask = mask.mul(float(1).sub(smoothstep(float(g.plane[2] * 0.8), float(g.plane[2]), off)));
    }
    if (g.bands) {
      const st = floor(gy.sub(y0).div(g.bands[0]));
      const inStorey = smoothstep(float(0.15), float(0.3), fract(gy.sub(y0).div(g.bands[0])));
      mask = mask.mul(f01(hash(st.add(Math.round(g.at[0]))).lessThan(g.bands[1]))).mul(inStorey);
    }
    let light = vec3(...g.colour).mul(g.k ?? 1);
    if (g.flood) {
      const keyG = clamp(dot(normalize(nw), normalize(vec3(0.45, 0.25, 0.85))), 0, 1);
      light = light.mul(dc).mul(keyG.mul(0.6).add(0.4));
    }
    return light.mul(mask);
  };
  // (dark may name its own band, [y0, y1]: the roof over a glowing wall, the whole sphere round a lit window band)
  // (night.glowBranch, Singapore M9: each glow in an If on its bounding cylinder, the circle and the height band with the
  // mask's 0.3 m edges, outside which its term is 0 exactly, so the sum is the same; the rest of the city skips them. Built
  // from copies of the inputs (a node first built inside a branch is declared in its scope only); a glow with a glass-block
  // grid (fwidth) is added outside the branches. Singapore's 13 building glows cost its night frames +10-19 % unbranched)
  if (N.glowBranch && bGlows.length) {
    const glowIn = { pw: positionWorld, nw: normalWorldGeometry, dc: diffuseColor.rgb };
    glowLit = Fn(() => {
      const V = Object.fromEntries(Object.entries(glowIn).map(([k, n]) => [k, n.toVar()]));
      const acc = vec3(0, 0, 0).toVar();
      for (const g of bGlows) {
        if (g.grid) { acc.addAssign(glowTerm(g, V.pw, V.nw, V.dc)); continue; }
        // (the circle tested as glowMask does, so a pixel on its rim falls the same way in both)
        const inside = length(V.pw.xz.sub(vec2(g.at[0], g.at[1]))).lessThan(g.r).and(V.pw.y.greaterThan(g.y[0] - 0.3)).and(V.pw.y.lessThan(g.y[1] + 0.3));
        If(inside, () => { acc.addAssign(glowTerm(g, V.pw, V.nw, V.dc)); });
      }
      return acc;
    })();
    for (const g of bGlows) if (g.dark) glowDark = max(glowDark, glowMask({ at: g.at, r: g.r, y: Array.isArray(g.dark) ? g.dark : g.y }));
  } else for (const g of bGlows) {
    const gy = positionWorld.y, [y0] = g.y;
    let mask = glowMask(g, normalWorldGeometry, diffuseColor.rgb);
    if (g.shell) {
      const d = length(positionWorld.sub(vec3(...(g.hub ?? [g.at[0], (g.y[0] + g.y[1]) / 2, g.at[1]]))));
      mask = mask.mul(smoothstep(float(g.shell[0] - 0.2), float(g.shell[0] + 0.2), d)).mul(float(1).sub(smoothstep(float(g.shell[1] - 0.2), float(g.shell[1] + 0.2), d)));
    }
    if (g.plane) {
      const off = abs(dot(positionWorld.xz.sub(vec2(g.at[0], g.at[1])), vec2(g.plane[0], g.plane[1])));
      mask = mask.mul(float(1).sub(smoothstep(float(g.plane[2] * 0.8), float(g.plane[2]), off)));
    }
    if (g.bands) {
      const st = floor(gy.sub(y0).div(g.bands[0]));
      const inStorey = smoothstep(float(0.15), float(0.3), fract(gy.sub(y0).div(g.bands[0])));
      mask = mask.mul(f01(hash(st.add(Math.round(g.at[0]))).lessThan(g.bands[1]))).mul(inStorey);
    }
    // (dark may name its own band, [y0, y1]: the roof over a glowing wall, the whole sphere round a lit window band)
    if (g.dark) glowDark = max(glowDark, glowMask({ at: g.at, r: g.r, y: Array.isArray(g.dark) ? g.dark : g.y }));
    let light = vec3(...g.colour).mul(g.k ?? 1);
    if (g.flood) {
      const keyG = clamp(dot(normalize(normalWorldGeometry), normalize(vec3(0.45, 0.25, 0.85))), 0, 1);
      light = light.mul(diffuseColor.rgb).mul(keyG.mul(0.6).add(0.4));
    }
    glowLit = glowLit.add(light.mul(mask));
  }
  const own = emissive.add(crownLit.mul(crownMask)).add(glassHall);
  return { emissive: ((N.glows ?? []).some((g) => g.dark) ? own.mul(float(1).sub(glowDark)) : own).add(glowLit), rooms, shops: shopsOf(true), wash, feature, bShare };
}
