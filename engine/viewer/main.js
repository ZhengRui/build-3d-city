// The city viewer: streams every tile (buildings with procedural facades, roads, bridges), nearest the view
// first, plus the ground. Renders on demand (nothing while idle but moving water, see below), at reduced
// resolution while the view moves. The engine is generic: the page is the city's web/ folder, whose city.json
// (city.js: title, About, latitude and season of the sun, wind, conventions, what is on...) and data folders
// (tiles, blocks, markings, trees, shores, cars, rooftops: links into ../../data/<city>/) make it that city.
import * as THREE from 'three/webgpu';
import { MapControls } from 'three/addons/controls/MapControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { SkyMesh } from 'three/addons/objects/SkyMesh.js';
import { ssao } from 'three/addons/tsl/display/SSAONode.js';
import { bloom } from 'three/addons/tsl/display/BloomNode.js';
import { pass, mrt, normalView, packNormalToRGB, unpackRGBToNormal, sample, screenUV, builtinAOContext, vec4, mix, float, smoothstep,
  logarithmicDepthToViewZ, perspectiveDepthToViewZ, cameraNear, cameraFar, fog, reference, positionView, positionWorld, varying, select, PCFShadowFilter, output,
  uniform, Fn, vec3, pmremTexture, cameraPosition, texture, screenCoordinate, ivec2, positionGeometry, floatBitsToUint, uint, luminance } from 'three/tsl';
// the engine's own modules, with the query the page gave main.js (a reload runs the current code), fetched side
// by side: awaited one by one they made a chain of eleven round trips before anything else started
const q = new URL(import.meta.url).search;
const [
  { createFacadeMaterial, createCityReflection, makeBillboardAtlas }, { createGroundMaterials, setCover, setCoverLines, coverWater },
  { createSeaMaterial, createInlandWaterMaterial, shoreField, renderWaterReflection, setWaterReflection, waterInView, setWaterTime, configureWater, setMirrorCull, mirrorStats, MIRROR_LAYER },
  { createTrees }, { createCars }, { createRooftops }, { createMenu }, { loadShores }, { loadTerrain }, { createNight }, { loadCity, sunAt },
  { createLatticeMaterial, createMasts }, { loadLamps, createLamps }, { createMassesMaterial }, { createShadowTrim, SHADOW_ONLY_LAYER },
  { loadPreset, resolveStyles },
] = await Promise.all(['facade', 'ground', 'water', 'trees', 'cars', 'rooftops', 'ui', 'shores', 'terrain', 'night', 'city', 'lattice', 'lamps', 'masses', 'shadows', 'styles']
  .map((m) => import(`./${m}.js${q}`)));
// (performance marks for measuring the load, eval's measure.mjs: modules, gpu, ground in, near in, compiled,
// first frame, all in)
performance.mark('modules');

// the city: city.json next to the page, over the engine's defaults (city.js); its name and About text into
// the page
const city = await loadCity();
// the facade styles' preset (styles.js, styles/<preset>.json): fetched now, resolved once tiles.json names the styles
const facadePreset = loadPreset(city.facade.preset ?? 'china-south');
document.title = city.title;
{
  const title = document.getElementById('title');
  if (city.nativeTitle) {
    const span = document.createElement('span');
    span.textContent = `· ${city.title}`;
    title.append(`${city.nativeTitle} `, span);
  } else title.textContent = city.title;
  document.getElementById('about').textContent = city.about;
  // the always-visible credit line (city.json "attribution"): plain text with [label](https://url) links and
  // [label](#about), which opens the menu's About (ui.js); built from text nodes, never parsed as HTML
  const credit = document.getElementById('attribution');
  if (city.attribution) {
    for (const part of city.attribution.split(/(\[[^\]]+\]\((?:https?:\/\/[^)\s]+|#about)\))/)) {
      const m = /^\[([^\]]+)\]\((.+)\)$/.exec(part);
      if (!m) { credit.append(part); continue; }
      const a = document.createElement('a');
      a.textContent = m[1];
      a.href = m[2];
      if (m[2] !== '#about') { a.target = '_blank'; a.rel = 'noopener noreferrer'; }
      credit.append(a);
    }
    credit.hidden = false;
    document.body.classList.add('has-attribution');
  }
}

// web/tiles links to ../../data/<city>/tiles (git-ignored), so the city's web/ folder alone can be served;
// web/blocks to ../../data/<city>/blocks, the same tiles and the road markings bundled (07b_blocks.py;
// ?blocks=0: the separate files)
const TILES = new URLSearchParams(location.search).get('tiles') ?? 'tiles/';
const BLOCKS = new URLSearchParams(location.search).get('blocks') ?? 'blocks/';
// a data folder's index file, revalidated on every load (no old copy after a rebuild); index.html has fetched the
// default ones already (window.__earlyJson)
const fetchIndex = (url) => window.__earlyJson?.[url] ?? fetch(url, { cache: 'no-cache' });
// compass azimuth (0 = north, 90 = east) and elevation -> scene direction (north is -z)
const compass = (azDeg, elDeg) => {
  const az = THREE.MathUtils.degToRad(azDeg), el = THREE.MathUtils.degToRad(elDeg);
  return new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el));
};
const params = new URLSearchParams(location.search);
// (?warmlog=1: what the shader preparation asked of the driver and when, for finding a stall: __viewer.warmLog,
// [ms, what, ...]: 'link' a program asked for (programs queued after it, the mode, the warm-up's light, the material),
// 'linked' (ms it took, programs still queued), 'step' a warm-up round (steps left, light, round, promises, complete,
// programs linked), 'lazy' a frame's new pipelines, 'light'; without KHR_parallel_shader_compile 'linksync', 'compile')
const warmLog = params.get('warmlog') === '1' ? [] : null;
const wlog = warmLog ? (...a) => { warmLog.push([Math.round(performance.now()), ...a]); } : () => {};
// (what is preparing, for the log: prep and warmLight are declared further down, after the first pipelines)
const wwho = () => { try { return [prep.mode, warmLight]; } catch { return ['init', null]; } };
// the sun at the start (compass azimuth, elevation in degrees; the menu sets the hour's at once)
const SUN = sunAt(params.has('time') ? Number(params.get('time')) : city.time.start, city.location.latitude, city.sun.declination,
  city.time.solarShift);
// what is on: ?<param>=0 turns it off, any other value on, none leaves the city's choice (city.json features)
const feature = (param, name) => (params.has(param) ? params.get(param) !== '0' : city.features[name]);
// ?night=0 (for measuring what the night costs by day): no street lamps and no night shaders compiled ahead
// (a change of light then prepares them as it is drawn)
const NIGHT_WARM = params.get('night') !== '0';
// a view starting after dark compiles its passes ahead too, as by day, before the loading screen goes (Paris M9
// round 4: drawn lazily instead, the first frame came 3-5 s sooner but nearly empty, 6 draws at the overview, and
// the view filled in for 8-14 s; ahead, the first frame is complete). ?nightcompile=0: lazily, as before
const NIGHT_AHEAD = params.get('nightcompile') !== '0';

// viewer settings, changed from the menu (ui.js). resolution: device pixels per CSS pixel, up to 2x,
// both still and moving (on-demand rendering and throttled shadows keep the GPU cool); the menu or
// ?moving=1.5 lowers it if it runs hot
const settings = {
  resolution: Math.min(devicePixelRatio, 2),
  movingResolution: Math.min(devicePixelRatio, Number(params.get('moving')) || city.movingResolution),
  ao: feature('ao', 'occlusion'),
  haze: city.sliders.haze,             // multiplies the haze density (menu slider)
  markings: feature('markings', 'markings'),
  traffic: feature('traffic', 'traffic'),   // cars, moving along their lanes (cars.js); ?traffic=0: none
  rooftops: feature('roofs', 'rooftops'),  // rooftop clutter (rooftops.js); ?roofs=0 or the menu turns it off
  trackpad: false,                     // set by the menu (remembered per browser, default on)
  time: params.has('time') ? Number(params.get('time')) : undefined,   // ?time=21: start at that hour
};
// The time slider dragged (not a shortcut): when its last input came (setSun), for the two rules below.
// - TIME_REST (on by default; ?timerest=0: off): while a change of light is held under the cover and the slider is
//   still being dragged, nothing is drawn or prepared until it has rested TIME_REST_MS; then the held rounds prepare the
//   light it landed on. Dragged from 16:00 to 22:00 during the warm-up the frames under the cover (never seen) had
//   linked the programs of each light it passed, dusk's by the sun and then the moon's, a moving frame at a time,
//   and the GPU drew every one of them (Singapore M9 critic: 10.3 s of nothing new on WebGL 2). Only when the work is
//   done changes: the frames shown are the same.
// - city.json time.sliderResolution (off by default; ?sliderres=): while the slider is dragged, the moving frames at
//   this resolution (at most the moving one), as while orbiting where movingResolution is lower: Singapore keeps 2x
//   for orbits, and a drag of the sun ran ~5 frames a second on WebGPU. The settled frame after is unchanged
let timeDragAt = -Infinity;
const TIME_REST = params.get('timerest') !== '0', TIME_REST_MS = 250;
let SLIDER_RES = Number(params.get('sliderres')) || city.time.sliderResolution || null;   // (__viewer.sliderRes(r): in-page A/B)
// ?webgl=1: the WebGL 2 backend even where WebGPU is available (testing both backends in one browser)
// Depth: reversed (float depth, far = 0) on WebGPU, logarithmic only on WebGL 2 (?depth=log forces it). A logarithmic
// depth buffer writes each fragment's depth from its shader, which turns off the GPU's early depth test: every
// fragment of every wall behind the front one ran the whole facade shader (Paris M9: the night street at 1,000 ms,
// 470 with reversed depth). Reversed float depth keeps the same precision from 2 m to 120 km without it
// WebGPU only where an adapter is given, not wherever navigator.gpu exists: Chrome on Linux without its Vulkan flags
// has navigator.gpu but no adapter, three fell back to WebGL 2 by itself, and the renderer had been made for WebGPU's
// reversed depth: the plain frames were right, but every frame through the occlusion pipeline (settled frames
// within 6 km of the target, the moving ones until the plain pass was prepared) came out empty, the page's dark
// background (Berlin fix round: "the page becomes black when idle, zoomed in", every city). Asked once more by three's
// own fallback; a few ms
const gpuAdapter = params.get('webgl') === '1' || !navigator.gpu ? null : await navigator.gpu.requestAdapter().catch(() => null);
const forceWebGL = !gpuAdapter;
const reversedDepth = !forceWebGL && params.get('depth') !== 'log';
const renderer = new THREE.WebGPURenderer({ antialias: true, logarithmicDepthBuffer: !reversedDepth, reversedDepthBuffer: reversedDepth, forceWebGL });
renderer.setPixelRatio(settings.resolution);
renderer.setSize(innerWidth, innerHeight);
// Khronos PBR Neutral keeps hues true (ACES shifted them and crushed the haze)
renderer.toneMapping = THREE.NeutralToneMapping;
const EXPOSURE = 0.9;                  // by day; raised after sunset (setSun)
renderer.toneMappingExposure = EXPOSURE;
// (the night's exposure factor, setSun; city.json night.highExposure, see the frame below)
let nightExposure = 1;
const HIGH_EXPOSURE = city.night?.highExposure ?? null;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
document.body.appendChild(renderer.domElement);
await renderer.init();
// (the GPU lost: WebGL 2's context or WebGPU's device; __viewer.lost(): its info, or null; leaving: the page let it
// go itself, see pagehide)
let deviceLost = null, leaving = false;
{
  const onLost = renderer.onDeviceLost;
  renderer.onDeviceLost = function (info) {
    deviceLost ??= { t: Math.round(performance.now()), api: info.api, message: info.message, reason: info.reason };
    wlog('lost', info.message);
    // (left alone the canvas froze on its last frame and nothing said why: the GPU process gone, Berlin M9 fix round)
    if (!leaving) {
      const el = document.getElementById('lost');
      if (el) { el.hidden = false; el.querySelector('button').onclick = () => location.reload(); }
      document.getElementById('note')?.setAttribute('hidden', '');
      document.getElementById('loading')?.setAttribute('hidden', '');
    }
    return onLost.call(this, info);
  };
}
// WebGL 2: the pipelines compiled in the background (KHR_parallel_shader_compile) are completed (_completeCompile:
// the program's uniform blocks and locations looked up) when the driver reports them done. three r186 polls each
// program on requestAnimationFrame, so every program finished by then was completed inside the one rAF task the
// view's frame runs in too (London M9's load profile: _completeCompile 4.8 s of main thread). Here they are polled
// from tasks of their own, each completing what is done for at most COMPLETE_MS (at least one). In London M9 round
// 2's five WebGL loads no completion took over 20 ms; the long tasks came from asking for too many programs at once
// (WARM_NEW, below). (?glpace=0: three's own way; __viewer.glCompletes: completions over 20 ms, [ms, ms])
const glCompletes = [];
let glWaiting = null;                        // (programs the driver is still compiling: see GL_QUEUE)
if (renderer.backend.isWebGLBackend && renderer.backend.parallel && params.get('glpace') !== '0') {
  const be = renderer.backend, gl = be.gl, parallel = be.parallel, COMPLETE_MS = 12;
  const waiting = glWaiting = [];            // [program, render object, pipeline, resolve]
  let polling = false;
  const poll = () => {
    const t0 = performance.now();
    for (let i = 0; i < waiting.length;) {
      if (i > 0 && performance.now() - t0 > COMPLETE_MS) break;
      const w = waiting[i];
      if (!gl.getProgramParameter(w[0], parallel.COMPLETION_STATUS_KHR)) { i++; continue; }
      waiting.splice(i, 1);
      const t = performance.now();
      be._completeCompile(w[1], w[2]);
      const d = performance.now() - t;
      wlog('linked', Math.round(t - w[4]), Math.round(d), waiting.length);
      if (d > 20) glCompletes.push([Math.round(t), Math.round(d)]);
      w[3]();
      if (performance.now() - t0 > COMPLETE_MS) break;
    }
    // (a task of its own, soon after: a setTimeout, not the next animation frame, whose task the view's frame shares)
    if (waiting.length) setTimeout(poll, 8); else polling = false;
  };
  const createPipeline = be.createRenderPipeline;
  be.createRenderPipeline = function (renderObject, promises) {
    if (promises === null) return createPipeline.call(this, renderObject, promises);
    // (three's createRenderPipeline up to its promise)
    const pipeline = renderObject.pipeline, { fragmentProgram, vertexProgram } = pipeline;
    const programGPU = gl.createProgram();
    const fragmentShader = this.get(fragmentProgram).shaderGPU, vertexShader = this.get(vertexProgram).shaderGPU;
    gl.attachShader(programGPU, fragmentShader);
    gl.attachShader(programGPU, vertexShader);
    gl.linkProgram(programGPU);
    this.set(pipeline, { programGPU, fragmentShader, vertexShader });
    promises.push(new Promise((resolve) => {
      waiting.push([programGPU, renderObject, pipeline, resolve, performance.now()]);
      wlog('link', waiting.length, ...wwho(), renderObject.material?.name || renderObject.material?.type);
      if (!polling) { polling = true; setTimeout(poll, 0); }
    }));
  };
}
// (?warmlog=1 without KHR_parallel_shader_compile: each program compiled and linked at once, timed)
if (warmLog && renderer.backend.isWebGLBackend && !renderer.backend.parallel) {
  const be = renderer.backend, create = be.createRenderPipeline, createProgram = be.createProgram;
  be.createRenderPipeline = function (renderObject, promises) {
    const t = performance.now(); const r = create.call(this, renderObject, promises);
    wlog('linksync', Math.round(performance.now() - t), ...wwho(), renderObject.material?.name || renderObject.material?.type);
    return r;
  };
  be.createProgram = function (program) {
    const t = performance.now(); const r = createProgram.call(this, program);
    wlog('compile', Math.round(performance.now() - t), program.stage);
    return r;
  };
}
// WebGL 2: every new pipeline is a program compiled and linked (one createRenderPipeline). Counted, so that a
// preparation round or a frame after the first view asks for at most a few (prep.maxLinks, GL_QUEUE): see the
// warm-up below
// Without KHR_parallel_shader_compile the link is done when createRenderPipeline returns: one that took under
// LINK_FREE_MS (a program the driver had already, such as a pipeline made again for another render object) is not
// counted, so it doesn't use up a round's or a frame's one link. linkMs: the main thread's time in those links (the
// warm-up's link budget, WARM_LINK_MS)
const LINK_FREE_MS = 3;
let linksMade = 0, linkMs = 0;
if (renderer.backend.isWebGLBackend) {
  const be = renderer.backend, create = be.createRenderPipeline;
  if (be.parallel) be.createRenderPipeline = function (...a) { linksMade++; return create.apply(this, a); };
  else {
    be.createRenderPipeline = function (...a) {
      const t = performance.now();
      try { return create.apply(this, a); } finally {
        const d = performance.now() - t;
        linkMs += d;
        if (d >= LINK_FREE_MS) linksMade++;
      }
    };
  }
}
performance.mark('gpu');

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 2, 120000);
const controls = new MapControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = THREE.MathUtils.degToRad(86);
controls.minDistance = 30;
controls.maxDistance = 60000;
// The controls take a trackpad's pinch (a wheel event with ctrlKey) as ten times a wheel step, unless they saw the
// Control key go down (then it's a real ctrl+wheel). A Control keyup that never reaches the page (macOS's screenshot
// keys, Cmd+Ctrl+Shift+4: the overlay takes the keyboard) left that flag set, and pinch zoom ten times slower until a
// reload (the user, 7 Oct: "a global sudden change after some freeze"). The flag is cleared whenever the page loses focus
// or a pointer moves without Control held
const controlUp = (e) => { if (!e.ctrlKey) controls._controlActive = false; };
addEventListener('blur', () => { controls._controlActive = false; });
addEventListener('pointermove', controlUp, { passive: true, capture: true });
addEventListener('pointerdown', controlUp, { passive: true, capture: true });

// Colour stays finite in the frame's half-float targets. Written to a half float, a value over 65504 is clamped to
// 65504 by Intel's Vulkan driver but becomes Inf on Apple's Metal (round to nearest), and Inf turns NaN in tone
// mapping, blurs and mips (Inf - Inf, Inf x 0). The sky's sun disc alone is ~60,800 (three's SkyMesh: min(sunE x Fex,
// 80) x 760) plus the sky round it. So the skies' output is held at 65504 (what Intel stored anyway: no change there),
// and a NaN there reads as 0 (finiteChannel: a bit test, as the shader compilers may assume finite floats and fold
// x != x away). A non-finite texel in the sky map (envSky, below) poisons its blur levels around it, and the day haze
// takes its colour from that map in the view's azimuth: the haze over a strip of the view towards the sun turned
// black, the city in it dark and as if unhazed, while the view moved (the user's Mac, London and Berlin, 6 Oct; Haze 0 %
// cleared it; reproduced here with Inf put into the sky map's sky near the sun)
const HALF_MAX = 65504;
const isFinite1 = (x) => floatBitsToUint(x).bitAnd(uint(0x7f800000)).notEqual(uint(0x7f800000));
const finiteChannel = (x) => select(isFinite1(x), x, float(0));
// (raw: the sky's own colour node; __viewer.finiteSky(envSky, node) puts a debug node under the guard)
const finiteSky = (s, raw = s.material.colorNode) => {
  s.material.colorNode = vec4(finiteChannel(raw.r).min(HALF_MAX), finiteChannel(raw.g).min(HALF_MAX), finiteChannel(raw.b).min(HALF_MAX), raw.a);
  s.material.userData.rawColour = raw;
  s.material.needsUpdate = true;
};

// sky + sun
const sky = new SkyMesh();
finiteSky(sky);
sky.scale.setScalar(200000);
// (city.json's sky; by default hazy, with scattered fair-weather cloud)
for (const [k, v] of Object.entries(city.sky)) if (sky[k]) sky[k].value = v;
scene.add(sky);
const sunDir = compass(SUN.azimuth, SUN.elevation);
sky.sunPosition.value.copy(sunDir);
// dusk and night (night.js): the twilight and night sky over the SkyMesh, the city's lights by the hour, and
// the uniforms the facades, streets and cars light up with (city.json's night: the moon, the lights' hours)
// (?duskfix=0: the dusk light as before the blue hour's grade, night.duskGrade; for comparisons)
const night = createNight(params.get('duskfix') === '0' ? { ...city.night, duskGrade: false } : city.night);
night.extendSky(sky);
// the directional light: the sun, or the moon once the sun is below the horizon (night.js)
const lightDir = sunDir.clone();

const hemi = new THREE.HemisphereLight(0xc4d6e8, 0x7a705e, 1.1);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff1dc, 4.0);
sun.castShadow = city.features.shadows;
// The menu's Shadows switch (setShadows). Turning castShadow off made three dispose the light's shadow node and its
// depth texture while the cached day shaders still sampled them: switched on again, ShadowNode.updateShadow threw
// ("reading 'depthTexture'"), WebGPU reported the destroyed ShadowDepthTexture in a submit, and no frame reached the
// canvas after that (every city, every engine before the fix). So once on, castShadow stays on: off is the shadow's
// intensity at 0 (a uniform: no shader rebuilt, nothing disposed; every lookup returns 1, lit) and no shadow pass
// drawn (needsUpdate reads false while off); on is intensity 1 and the map drawn afresh
let shadowsOn = sun.castShadow;
{
  let due = sun.shadow.needsUpdate;
  Object.defineProperty(sun.shadow, 'needsUpdate', { get: () => due && shadowsOn, set: (v) => { due = v; }, configurable: true });
}
function setShadows(on) {
  shadowsOn = on;
  if (on && !sun.castShadow) sun.castShadow = true;   // (a city that starts without: its shaders built once, here)
  sun.shadow.intensity = on ? 1 : 0;
  sun.shadow.needsUpdate = true;
  invalidate({ shadows: true });
}
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.near = 10;
sun.shadow.camera.far = 12000;
sun.shadow.bias = -0.0004;
sun.shadow.normalBias = 1.5;
sun.shadow.autoUpdate = false;   // re-rendered only when the view has moved enough (updateSun)
// beyond the shadow camera's far plane: lit, with reversed depth too. three's shadow lookup counts a point as
// inside the shadow map when its depth there is <= 1, which leaves out what lies beyond the far plane with a
// 0-to-1 depth (> 1 there) but not with reversed depth, where far is 0 and beyond it negative: such a point was
// compared against the cleared map (0) and came out shadowed. From far above, ground more than 6 km beyond the
// view's target, seen from the sun, was a sharp-edged dark quadrilateral several km across (Paris overview, M9)
if (renderer.reversedDepthBuffer) sun.shadow.filterNode = (inputs) => select(inputs.shadowCoord.z.lessThan(0), float(1), PCFShadowFilter(inputs));
scene.add(sun, sun.target);
// city.json shadows (shadows.js; off by default): the ground layers cast through copies of their steep faces only
// (groundSteep), and tiles whose shadows can't fall in view are left out of the shadow pass (fit)
const SHADOW_OPTS = city.shadows ?? {};
const shadowTrimOn = SHADOW_OPTS.groundSteep != null || !!SHADOW_OPTS.fit;
const shadowTrim = shadowTrimOn ? createShadowTrim({ sun, opts: SHADOW_OPTS, mirrorY: city.water?.mirror ?? 0 }) : null;
if (shadowTrim) sun.shadow.camera.layers.enable(SHADOW_ONLY_LAYER);   // (its own layers then: 0 and the copies')
// the moon (night.js): a light of its own, casting no shadows, on instead of the sun once it is below the
// horizon. (Every lit shader sampling the sun's shadow map, which no longer mattered, cost the night some
// 7 %; turning the sun's castShadow off instead lost its shadows for good: the shaders cached for daylight
// kept the shadow node three.js disposes then.)
const moon = new THREE.DirectionalLight(0xa8bcff, 0);
moon.target = sun.target;
moon.visible = false;
scene.add(moon);
// aerial perspective: haze thickens with distance (exponential squared), by default about a quarter at 8 km
// and most of it by 20 km; the sky shader ignores fog. The colour is HDR, as bright as the sky's horizon
// before tone mapping, so land and sea melt into it instead of ending in a grey band (city.json's haze)
const HAZE = new THREE.Color().setRGB(...city.haze.colour);
const HAZE_DENSITY = city.haze.density, HAZE_LAYER = city.haze.layer;          // per metre; metres
scene.fog = new THREE.FogExp2(HAZE.clone(), HAZE_DENSITY);
// The same haze as a node, except that far out (beyond ~10 km, where hills are all there is to see) it thins
// with the height of what a sight line ends on: far hills (in Shenzhen those of Hong Kong and 梧桐山) rise
// above most of the haze and still show against the sky as they do from the city, while the plain melts
// into it. Near and low it is exactly the FogExp2 above (which the sea applies itself, water.js: it lies
// low, where the two agree).
const HAZE_THIN_H = city.haze.thinHeight;               // metres: at this height the far haze is halved
// After dark (while the lit copies of the materials are on, night.js) the fog adds the haze lit from below
// by the city, thickest low down, to the day's haze, in the night's haze colour (a node of its own, swapped
// in with the lit copies, so by day the fog is exactly the day's)
const fogNodes = {};
{
  const viewZ = positionView.z.negate();
  // (city.json haze.thinMin, opt-in, Tokyo M7 fix round: the thinning never below this share, so a far high summit
  // keeps some haze: Fuji at 98 km with thinHeight 250 stood almost unhazed, grey-green with every gully, where from
  // Tokyo it is a blue-violet silhouette. Unset: as before)
  let thinK = float(1).div(positionWorld.y.max(0).div(HAZE_THIN_H).add(1));
  if (city.haze.thinMin) thinK = thinK.max(city.haze.thinMin);
  const thin = mix(float(1), thinK, smoothstep(float(9000), float(22000), viewZ));
  const d = reference('density', 'float', scene.fog).mul(viewZ).mul(thin);
  const colour = reference('color', 'color', scene.fog);
  // city.json haze.edge [r0, r1] (m from the scene's origin; default off): the land fades wholly into the haze
  // between these radii, so the backdrop's rectangular outer edge never shows against the sky (London M7: seen
  // from the overview, 7 km up, the haze is thin and the land ended in a straight line at the top left)
  const edge = city.haze.edge ? smoothstep(float(city.haze.edge[0]), float(city.haze.edge[1]), positionWorld.xz.length()) : null;
  const withEdge = (f) => (edge ? f.max(edge) : f);
  fogNodes.day = scene.fogNode = fog(colour, withEdge(float(1).sub(d.mul(d).negate().exp())));
  // (worked out per vertex: it varies slowly, and per pixel it cost the night a few percent)
  fogNodes.night = fog(colour, withEdge(float(1).sub(d.mul(d).add(varying(night.u.hazeDepth(viewZ))).negate().exp())));
}
// the lit copies (and the night's fog) on or off
function nightOn(on = night.state.on) {
  lamps?.setOn(on);                          // the real street lamps (lamps.js), drawn only after dark
  night.apply(scene, on);
  night.apply(envScene, on);
  scene.fogNode = on ? fogNodes.night : fogNodes.day;
}

// materials
const mat = {
  land: new THREE.MeshStandardNodeMaterial({ color: 0xd9d3c4, roughness: 0.95 }),
  green: new THREE.MeshStandardNodeMaterial({ color: 0x86a86c, roughness: 0.95 }),
  water: new THREE.MeshStandardNodeMaterial({ color: 0x3f6f8f, roughness: 0.25 }),
  aeroway: new THREE.MeshStandardNodeMaterial({ color: 0x55595e, roughness: 0.9 }),
  sea: new THREE.MeshStandardNodeMaterial({ color: 0x3a6886, roughness: 0.3 }),
  road: new THREE.MeshStandardNodeMaterial({ vertexColors: true, roughness: 0.92 }),
  bridge: new THREE.MeshStandardNodeMaterial({ vertexColors: true, roughness: 0.85 }),
  lattice: createLatticeMaterial({ night: night.u }),   // open iron lattices: structures' braced panels (lattice.js), gilt at night
};
// procedural land, green, aeroway and road surfaces, and the road markings layer (06b_markings.py; web/markings
// links to ../../data/<city>/markings). Without markings.json the viewer runs without markings.
const MARKINGS = 'markings/';
// the city's real street lamps (06e_lamps; web/lamps, lamps.js): where its lighting inventory covers the
// streets they replace the procedural posts of the ground's materials (?lamps=0: procedural everywhere)
const [markingsIndex, lampsData] = await Promise.all([
  fetchIndex(MARKINGS + 'markings.json').then((r) => (r.ok ? r.json() : null)).catch(() => null),
  params.get('lamps') === '0' || !NIGHT_WARM ? null : loadLamps('lamps/').catch(() => null),
]);
const lamps = lampsData && createLamps(lampsData, { night: night.u, fog: scene.fog, ...(city.lamps ?? {}) });
if (lamps) scene.add(lamps.group);
mat.masses = createMassesMaterial(night.u, city.masses ?? {});   // the town beyond the districts as block masses (06e_masses.py)
// ground layers lie on one another (draped over the same terrain); lift overlays a little and draw them after
// the land (mudflats lie off the land, between the sea at -1 and the land at 0)
const LAYER_Y = { land: 0, town: 0, mud: -0.5, gravel: 0.3, asphalt: 0.25, paved: 0.35, green: 0.6, water: 0.9, aeroway: 1.2, backdrop: 0 };

const sea = new THREE.Mesh(new THREE.PlaneGeometry(400000, 400000), mat.sea);
sea.rotation.x = -Math.PI / 2;
sea.position.y = -1;
sea.receiveShadow = true;
// the sea is one huge quad, whose log depth is too coarse to lose reliably to land 1 m above it:
// draw it first as a backdrop that writes no depth, so land and everything else always cover it
sea.renderOrder = -1;
sky.renderOrder = -2;          // sky first of all, or it would paint over the depthless sea
mat.sea.depthWrite = false;
scene.add(sea);

// ---------------------------------------------------------------- on-demand rendering
let dirty = true, shadowDirty = true;
let animSlow = false;          // (the animation too slow at this view: see ANIM_SLOW_MS)
// whether the frame just drawn left something out for want of a shader (lazily; see presented)
let frameGaps = false;
// (redraw: the view hasn't changed, only what is in it: what was left out for want of a shader (lazily), tiles,
// trees, rooftops, cars and shores arriving, a jump in the light. A settled view is drawn settled again rather
// than at the moving frames' quality, which flickered between the two (and cost a frame more each time); and
// redraws are merged to at most one every REDRAW_MS, since arrivals come a few at a time while streaming)
let viewDirty = true;
const REDRAW_MS = 300;
let lastDrawnAt = 0;
// (?invallog=1: every request for a frame logged with its caller, __viewer.invalLog: what keeps an idle view drawing)
const invalLog = params.get('invallog') === '1' ? [] : null;
const invalidate = ({ shadows = false, redraw = false } = {}) => {
  if (invalLog && invalLog.length < 20000) invalLog.push([Math.round(performance.now()), redraw, new Error().stack.split('\n').slice(2, 6).map((l) => l.trim()).join(' < ')]);
  dirty = true; viewDirty ||= !redraw; shadowDirty ||= shadows;
};
const tileGroups = [];

// ---------------------------------------------------------------- loading
// The city streams in nearest the view first: the ground's TIN and the ground, then the building tiles and
// their road markings in 4 km blocks (07b_blocks.py), a few at a time, always the remaining block nearest the
// orbit target. The loading screen stays up, nothing drawn, until the ground and the blocks within NEAR of the
// target are in and their shaders compiled (compileOnly, without stalling); then the view shows and can be
// moved while the rest arrives, under a small progress bar. Trees, rooftops and cars stream by distance on
// their own (trees.js, rooftops.js, cars.js); the shores and the woods' far carpet follow once the view is up.
const [index, blocksIndex] = await Promise.all([
  fetchIndex(TILES + 'tiles.json').then((r) => r.json()),
  BLOCKS === '0' ? null : fetchIndex(BLOCKS + 'blocks.json').then((r) => (r.ok ? r.json() : null)).catch(() => null),
]);
// (made once tiles.json says whether the city has land cover maps and block masses: the backdrop's and the town
// layer's shaders hold only what the city uses, see ground.js)
Object.assign(mat, createGroundMaterials(markingsIndex, { sunDir, night: night.u, ground: city.ground, markings: city.markings,
  realLamps: lampsData?.mask, waterSky: reference('color', 'color', scene.fog),
  // (city.json ground.townPainted, opt-in, Hong Kong M7f: the town layer keeps its painted roofscape under the masses, as
// when there are none: 06e_masses' masses_min_h raises only the towers, the low town between them stays painted)
  area: { cover: !!index.cover, masses: city.ground?.townPainted ? false : index.tiles.some((t) => t.file.startsWith('m_')) } }));
// ?at=x,z,distance,elevation[,azimuth] (scene metres, degrees) looks at any spot; ?view=<name> picks a preset
const at = params.get('at')?.split(',').map(Number);
const startView = at?.length >= 4 ? { x: at[0], z: at[1], distance: at[2], elevation: at[3], ...(at.length > 4 ? { azimuth: at[4] } : {}) }
  : index.views.find((v) => v.name === (params.get('view')
    // a portrait screen (a phone held upright) opens at city.startViewPortrait where the city names one
    ?? (city.startViewPortrait && innerHeight > innerWidth * 1.2 ? city.startViewPortrait : city.startView))) ?? index.views[0];
// a preset with an hour (a dusk or night view) starts at it, unless ?time= says otherwise (the menu sets the sun)
if (settings.time === undefined && startView.time !== undefined) settings.time = startView.time;
const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);   // tiles are meshopt-compressed (07_pack.py)
MeshoptDecoder.useWorkers(Math.min(4, Math.max(1, (navigator.hardwareConcurrency ?? 4) >> 1)));   // (off the main thread)
// the ground's height (05a_terrain.py's TIN, terrain.js): what the trees, the orbit target and the camera
// stand on; tiles from before the terrain have none, and a flat ground
const terrainLoaded = index.terrain ? loadTerrain(loader, TILES + index.terrain)
  : Promise.resolve({ height: () => 0, ceiling: () => 0 });
// glass and water reflect the sky: a prefiltered copy of it, re-rendered into the same target when the
// sun moves, so every material sampling it follows
const envSky = new SkyMesh();
finiteSky(envSky);
for (const k of ['turbidity', 'rayleigh', 'mieCoefficient', 'mieDirectionalG', 'cloudCoverage', 'cloudDensity']) envSky[k].value = sky[k].value;
envSky.sunPosition.value.copy(sunDir);
envSky.showSunDisc.value = 0;              // direct sunlight comes from the light; the disc would flood the map
envSky.scale.setScalar(50);
night.extendSky(envSky);                  // glass and water reflect the dusk and night sky too
const envScene = new THREE.Scene();
envScene.add(envSky);
const pmrem = new THREE.PMREMGenerator(renderer);
const envTarget = pmrem.fromScene(envScene, 0, 0.1, 100);
// (made again, once a change of light has marked it, by the next frame drawn (updateEnv in the loop), never inside a
// preparation (prep.mode set: compileOnly's dry rounds turn the backend's beginRender, finishRender and clear into no-ops,
// and a lazy round leaves out what isn't built yet): made there it came out empty or half drawn and stayed so, the
// sky the water and glass reflect black below a bright rim, a black and white line along the sea's horizon on WebGL 2
// at a dusk start, New York's Downtown Brooklyn; the first minute's warm-up fix (8986ea9) had moved it into the
// preparation of the first view)
let envDirty = false;
const updateEnv = () => {
  if (!envDirty || prep.mode !== null) return;          // (prep: declared with the preparation, further down)
  envDirty = false;
  pmrem.fromScene(envScene, 0, 0.1, 100, { renderTarget: envTarget });
};
const envMap = envTarget.texture;
// city.json haze.height {density, scale, ramp, lift, sky, saturation} (default off: the FogExp2 haze above): by day, aerial
// perspective from a haze whose density falls off exponentially with height (density per metre at the ground,
// halved every scale x ln 2 m up), integrated along each sight line, so a ray from the Shard to the North Downs
// crosses its thick bottom, one from 7 km up over the overview mostly clear air, and a far hilltop stands above
// some of it. The optical depth grows as d² / (d + ramp) (clear nearby, linear far out), and the haze takes the
// colour of the sky just over the horizon in that direction (the sky PMREM `lift` up: hazy blue, bright towards
// the sun, warm at sunset), so far land fades into the sky behind it rather than under a flat grey or white cap.
// (London M7 fix round: the far land a dead-flat grey-green band beyond 10-12 km from the Shard, and from the
// overview land at 25-35 km as contrasty as at 5 km, then an abrupt white rim). The sea (water.js) applies the
// same. After dark the night's haze (fogNodes.night) is unchanged.
let hazeDay = null;
if (city.haze.height) {
  const { density = 6e-5, scale = 1200, ramp = 6000, lift = 0.04, sky: skyK = 1, saturation = 1, edgeSky = false } = city.haze.height;
  const k = uniform(1).onRenderUpdate(() => settings.haze);
  const edge = city.haze.edge ? smoothstep(float(city.haze.edge[0]), float(city.haze.edge[1]), positionWorld.xz.length()) : null;
  hazeDay = Fn(() => {
    const rel = positionWorld.sub(cameraPosition).toVar();
    const dist = rel.length().max(1).toVar();
    const hc = cameraPosition.y.max(0).div(scale), hp = positionWorld.y.max(0).div(scale);
    const a = hc.negate().exp(), b = hp.negate().exp();
    const dh = hp.sub(hc).toVar();
    // the mean density along the ray, relative to the ground's: (e^-hc - e^-hp) / (hp - hc)
    const mean = select(dh.abs().lessThan(1e-3), a, a.sub(b).div(select(dh.abs().lessThan(1e-3), float(1), dh)));
    const tau = float(density).mul(k).mul(mean).mul(dist.mul(dist).div(dist.add(ramp)));
    let amount = float(1).sub(tau.negate().exp());
    if (edge) amount = amount.max(edge);
    const look = rel.div(dist);
    // (haze.height.edgeSky (default false): over haze.edge's fade the colour turns to the sky's own in the view ray's
    // direction, at full strength and saturation, so the backdrop's rim, seen from high up under the horizon line,
    // melts into the sky drawn round it instead of bowing as an arc of haze colour against it (Berlin M7 fix round))
    const ek = edge && edgeSky ? edge : null;
    const dir = ek ? mix(vec3(look.x, lift, look.z), look, ek) : vec3(look.x, lift, look.z);
    // (a non-finite texel of the sky map (see finiteChannel): the flat haze colour instead. On a Mac with the haze
    // facing the sun a strip of the view's azimuths round the sun's came out unhazed and dark while the view moved,
    // London and Berlin, 6 Oct; Haze 0 % cleared it)
    const skyRaw = pmremTexture(envMap, dir.normalize(), float(0.05)).rgb;
    const skyOk = isFinite1(skyRaw.r).and(isFinite1(skyRaw.g)).and(isFinite1(skyRaw.b));
    const skyC = select(skyOk, skyRaw.min(HALF_MAX), reference('color', 'color', scene.fog));
    // (saturation: the clear-sky model's low sky is a cleaner cyan than a hazy horizon; less of its colour)
    let colour = mix(vec3(skyC.dot(vec3(0.2126, 0.7152, 0.0722))), skyC, saturation).mul(skyK);
    if (ek) colour = mix(colour, skyC, ek);
    return vec4(colour, amount);
  })();
  fogNodes.day = fog(hazeDay.rgb, hazeDay.a);
  if (!night.state.on) scene.fogNode = fogNodes.day;
}

// sun position (compass azimuth, elevation in degrees) and the hour (local solar time): sky, light colour
// and strength, reflections; after sunset the moon, the night sky and the city's lights (night.js)
// the sky light: its colour from above and the light bounced up from the ground (city.json light), and its
// strength by day
// (city.json light.skyColour: the sky light's colour; the default's pale blue tinted Paris's shaded asphalt navy)
const HEMI_SKY = new THREE.Color(city.light.skyColour ?? 0xc4d6e8), HEMI_GROUND = new THREE.Color(city.light.ground);
const HEMI_DAY = city.light.sky;
function setSun(azimuth, elevation, hour = 12, { jump = false } = {}) {
  if (!jump && shown) timeDragAt = performance.now();
  sunDir.copy(compass(azimuth, elevation));
  sky.sunPosition.value.copy(sunDir);
  envSky.sunPosition.value.copy(sunDir);
  const n = night.update(hour, azimuth, elevation);
  if (n.changed) {
    wlog('light', night.state.on);
    if (shown && hold === null) freezeView();   // (the view as it was stays on screen meanwhile)
    if (shown) { heldFresh = true; heldRounds = 0; heldDone = false; }
    nightOn();                                 // the lit copies of the materials on or off
    if (night.state.on) { glowMovingReady = false; glowPrep = null; }   // (see prepareMovingGlow)
    animSlow = false;                          // (the animation's cost differs by night: measured again)
  }
  // (the sky map made again once, before the next frame drawn, not at every input: dragging the time slider sent
  // ~60 a second, each a render of the sky and its blur levels queued on the GPU ahead of any frame; on WebGL 2 the
  // next call that waited for the GPU process stalled the page 2-3 s, Berlin's warm-up round)
  envDirty = true;
  cityReflection.markStale();                  // glass mirrors the city in the new light
  // low sun: warmer, weaker direct light and a dimmer sky
  const k = THREE.MathUtils.smoothstep(elevation, 2, 30);
  sun.color.setRGB(1, 0.72 + 0.23 * k, 0.5 + 0.36 * k);
  sun.intensity = 4 * THREE.MathUtils.smoothstep(elevation, -2, 12);
  // below the horizon the directional light is the moon, which casts no shadows: the sun is switched off
  // (its shadow map neither redrawn, updateSun, nor looked up; warmUpNight compiles the shaders for both)
  lightDir.copy(n.moon ? n.moon.dir : sunDir);
  sun.visible = !n.moon;
  moon.visible = !!n.moon;
  if (n.moon) { moon.color.copy(n.moon.color); moon.intensity = n.moon.intensity; }
  // the sky light fades through twilight into the night's: the city's warm glow from below, a dim sky above
  hemi.intensity = (0.35 + 0.75 * THREE.MathUtils.smoothstep(elevation, -4, 25)) * (HEMI_DAY / 1.1) * n.dayK + n.hemiNight;
  const w = n.hemiNight / Math.max(hemi.intensity, 1e-6);
  hemi.color.copy(HEMI_SKY).lerp(n.hemiSky, w);
  hemi.groundColor.copy(HEMI_GROUND).lerp(n.hemiGround, w);
  // the haze is lit by the same sky: dimmer and warmer as the sun goes down, then the colour of the
  // twilight horizon and the city's glow
  const f = 0.3 + 0.7 * THREE.MathUtils.smoothstep(elevation, -2, 25);
  scene.fog.color.copy(HAZE).multiplyScalar(f).multiply(new THREE.Color().setRGB(1, 0.93 + 0.07 * k, 0.82 + 0.18 * k))
    .multiplyScalar(n.fogDayK).add(n.fog.multiplyScalar(1 - n.fogDayK));
  renderer.toneMappingExposure = EXPOSURE * n.exposure;
  nightExposure = n.exposure;
  // a jump (the menu's Day, Dusk, Night) or a change between day and night: one settled frame in the new light,
  // its shadows fresh, rather than a moving frame first and the settled one 250 ms later (two changes seen);
  // dragging the time slider moves like the camera
  // (just after a move the view may still count as moving for up to 250 ms: settled at once, unless input is
  // still coming, so the new light isn't a soft moving frame first and the sharp one after)
  if ((jump || n.changed) && moving && performance.now() - lastInput > 50) {
    moving = false;
    renderer.setPixelRatio(settings.resolution);
  }
  invalidate({ shadows: true, redraw: jump || n.changed });
}
// water reflects the same sky (water.js), waves raised by the city's wind; the sea keeps its depthless
// backdrop trick
configureWater(city.water);
mat.sea = sea.material = createSeaMaterial(envMap, scene.fog, { sunDir, night: night.u, edge: city.haze.edge, haze: hazeDay });
mat.sea.depthWrite = false;
mat.water = createInlandWaterMaterial(envMap, { sunDir, night: night.u });
// glass mirrors the city around the orbit target, captured into a cube map on settled frames (facade.js);
// ?reflect-city=0: glass reflects the sky only
settings.cityMirror = feature('reflect-city', 'cityReflections');
// city.json facade.probe (off by default; New York and Shenzhen capture as they always did): glassOnly: a capture only
// while glass covers glassShare of the screen or more, counting the tiles in view within glassNear metres of the probe
// (glassInView), else the last capture kept or none; lean: the faces without what a 256-pixel reflection can't show (town masses, road
// markings, the real street lamps; trees, rooftops and cars are always left out) and with the tiles within `reach`
// metres (their nearest point) only. ?probeglass=0|1 and ?probelean=0|1 override them, for comparisons
const PROBE = { ...city.facade.probe };
if (params.has('probeglass')) PROBE.glassOnly = params.get('probeglass') !== '0';
if (params.has('probelean')) PROBE.lean = params.get('probelean') !== '0';
if (params.has('probereach')) PROBE.reach = Number(params.get('probereach'));
const cityReflection = createCityReflection(renderer, envMap, { height: city.facade.probeHeight,
  ...(PROBE.lean ? { reach: PROBE.reach, nearest: true } : {}) });
// (lean) the shores (seawalls, banks, beaches, shallows: 0.7 M triangles in Paris) are left out of the faces too, and the
// whole-region ground layers, which every face drew whole (2.5 M triangles a face in Paris: green, town, land...), draw
// only the PROBE_CELL cells within groundReach metres of the probe: each big layer's triangles are sorted by cell (rows
// of cells, so the cells of a row within reach are one run) when it arrives, and a copy of the mesh over the same
// buffers, drawn only in the probe, gets one group per row
let probeShores = null;
const PROBE_CELL = 1000, probeGround = [];
function probeCells(o) {
  const g = o.geometry, idx = g.index?.array, pos = g.attributes.position;
  if (!idx || idx.length < 3 * 50000) return;           // (small layers are drawn whole)
  o.updateWorldMatrix(true, false);
  const nf = idx.length / 3, v = new THREE.Vector3(), cx = new Float32Array(pos.count), cz = new Float32Array(pos.count);
  for (let i = 0; i < pos.count; i++) { v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld); cx[i] = v.x; cz[i] = v.z; }
  const key = new Int32Array(nf), counts = new Map();
  for (let f = 0; f < nf; f++) {
    const a = idx[3 * f], b = idx[3 * f + 1], c = idx[3 * f + 2];
    const col = Math.floor((cx[a] + cx[b] + cx[c]) / 3 / PROBE_CELL), row = Math.floor((cz[a] + cz[b] + cz[c]) / 3 / PROBE_CELL);
    const k = (row + 5000) * 10000 + (col + 5000);
    key[f] = k;
    counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  const keys = [...counts.keys()].sort((a, b) => a - b);
  const start = new Map();
  let o3 = 0;
  for (const k of keys) { start.set(k, o3); o3 += 3 * counts.get(k); }
  const out = new idx.constructor(idx.length), fill = new Map(start);
  for (let f = 0; f < nf; f++) {
    let p = fill.get(key[f]);
    out[p++] = idx[3 * f]; out[p++] = idx[3 * f + 1]; out[p++] = idx[3 * f + 2];
    fill.set(key[f], p);
  }
  idx.set(out);
  // rows: [row, [col, start, count]...] in index order
  const rows = [];
  for (const k of keys) {
    const row = Math.floor(k / 10000) - 5000, col = (k % 10000) - 5000;
    if (rows.at(-1)?.row !== row) rows.push({ row, cells: [] });
    rows.at(-1).cells.push([col, start.get(k), 3 * counts.get(k)]);
  }
  probeGround.push({ o, m: null, rows });
}
// (the copy made at the first capture: the water's layers get attributes of their own after this, water.js shoreField)
function probeCopy(o) {
  const g = o.geometry, geo = new THREE.BufferGeometry();
  for (const [name, a] of Object.entries(g.attributes)) geo.setAttribute(name, a);
  geo.setIndex(g.index);
  geo.boundingSphere = g.boundingSphere ?? (g.computeBoundingSphere(), g.boundingSphere);
  const m = new THREE.Mesh(geo, [o.material]);
  m.name = `${o.name}-probe`;
  m.position.copy(o.position); m.quaternion.copy(o.quaternion); m.scale.copy(o.scale);
  m.castShadow = false;
  m.receiveShadow = o.receiveShadow;
  m.renderOrder = o.renderOrder;
  m.visible = false;
  m.userData.probeCopy = true;
  o.parent.add(m);
  return m;
}
// before a lean capture from p: the ground layers' copies with the rows of cells within reach, the layers hidden; undone after
function probeGroundIn(p) {
  const R = PROBE.groundReach, shown = [];
  for (const pg of probeGround) {
    const { o, rows } = pg;
    if (!o.visible) continue;
    const m = (pg.m ??= probeCopy(o));
    m.material[0] = o.material;               // (night.js may have swapped the layer's material)
    m.geometry.clearGroups();
    for (const { row, cells } of rows) {
      const dz = Math.max(row * PROBE_CELL - p.z, 0, p.z - (row + 1) * PROBE_CELL);
      if (dz > R) continue;
      let s0 = -1, s1 = -1;
      for (const [col, st, n] of cells) {
        if (Math.hypot(Math.max(col * PROBE_CELL - p.x, 0, p.x - (col + 1) * PROBE_CELL), dz) > R) continue;
        if (s0 < 0) s0 = st;
        s1 = st + n;
      }
      if (s0 >= 0) m.geometry.addGroup(s0, s1 - s0, 0);
    }
    o.visible = false;
    m.visible = true;
    shown.push(o);
  }
  return () => { for (const o of shown) o.visible = true; for (const { m } of probeGround) if (m) m.visible = false; };
}
// the city's facade styles: the preset's data for each style in tiles.json, with city.json's changes (styles.js)
await facadePreset;
const facadeStyles = await resolveStyles(index.styles, city);
// billboard art for the signs style (billboards.js), drawn once if the city has any
const billboards = Object.values(facadeStyles.styles).some((d) => d.billboards) ? makeBillboardAtlas(city.facade.billboards) : null;
mat.buildings = createFacadeMaterial(index, envMap, Number(params.get('reflect')) || undefined, cityReflection, night.u,
  { ...facadeStyles.facade, styles: facadeStyles.styles, billboards, streetLight: lampsData?.streetLight });  // ?reflect= tunes glass
const glassReflect = mat.buildings.userData.reflect.value, waterReflect = mat.sea.userData.reflect?.value ?? 1;

// ?masses=0: without the town masses (06e_masses), for comparisons (the markings tiles are m_<i>_<j> too: until
// Paris M7's fix ?masses=0 dropped them as well)
const noMasses = params.get('masses') === '0';
settings.masses = !noMasses;   // the menu's Towns switch hides them (cullTiles); ?masses=0 doesn't load them
// the blocks and the glbs in each (parts): from blocks.json, or else one per tile and per markings tile
const tileInfo = { tiles: new Map(index.tiles.map((t) => [t.file, t])), markings: new Map((markingsIndex?.tiles ?? []).map((t) => [t.file, t])) };
const blocks = blocksIndex
  ? blocksIndex.blocks.map((b) => ({ url: BLOCKS + b.file, gzip: true, x: b.x, z: b.z, size: b.size ?? blocksIndex.size, late: !!b.late,
    parts: b.parts.filter(([kind, file]) => (kind === 'tiles' || markingsIndex) && !(noMasses && kind === 'tiles' && file.startsWith('m_'))).map(([kind, file, offset, length]) => ({ kind, file, offset, length })) }))
  : [...index.tiles.map((t) => ({ url: TILES + t.file, x: t.x, z: t.z, size: t.size, parts: [{ kind: 'tiles', file: t.file }] })),
    ...(markingsIndex?.tiles ?? []).map((t) => ({ url: MARKINGS + t.file, x: t.x, z: t.z, size: t.size, parts: [{ kind: 'markings', file: t.file }] }))];
const blockDistance = (b, p) => Math.hypot(Math.max(b.x - p.x, 0, p.x - b.x - b.size), Math.max(b.z - p.z, 0, p.z - b.z - b.size));
// the view shows once the blocks this close to its target are in (what fills the view in front of the camera)
const NEAR = Math.max(2500, startView.distance);
// (city.json loading.frustumNear: only those the start view's camera sees, the rest right after it shows; the
// ground under a block up to 400 m, its tallest towers)
// (?early=, ?defer=, ?fnear= 0 or 1 override them, for comparisons)
const loadingFlag = (param, name) => (params.has(param) ? params.get(param) !== '0' : !!city.loading[name]);
const LOADING = { earlyCompile: loadingFlag('early', 'earlyCompile'), deferLayers: loadingFlag('defer', 'deferLayers'),
  frustumNear: loadingFlag('fnear', 'frustumNear'), passesLater: loadingFlag('later', 'passesLater') };
// (a far start view's settled frame is itself drawn without occlusion: nothing to leave for later then)
if (!settings.ao || startView.distance > 6000) LOADING.passesLater = false;
const seenFromStart = (() => {
  if (!LOADING.frustumNear) return () => true;
  const cam = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 2, 120000);
  const t = new THREE.Vector3(startView.x, startView.y ?? 0, startView.z);
  cam.position.copy(t).addScaledVector(compass(startView.azimuth ?? city.camera.azimuth, startView.elevation), startView.distance);
  cam.lookAt(t);
  cam.updateMatrixWorld();
  const frustum = new THREE.Frustum().setFromProjectionMatrix(new THREE.Matrix4().multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse));
  const box = new THREE.Box3();
  return (b) => frustum.intersectsBox(box.set(new THREE.Vector3(b.x, -50, b.z), new THREE.Vector3(b.x + b.size, 400, b.z + b.size)));
})();
// (late blocks, the town masses of 06e_masses: after the view shows, last of all)
for (const b of blocks) b.near = !b.late && blockDistance(b, startView) < NEAR && seenFromStart(b);

// progress: the ground and every glb; until the view shows, of those it waits for
const loadingEl = document.getElementById('loading');
const bar = document.querySelector('#bar div');
const loadtext = document.getElementById('loadtext');
const count = { done: 0, total: 1, nearDone: 0, nearTotal: 1 };
for (const b of blocks) {
  count.total += b.parts.length;
  if (b.near) count.nearTotal += b.parts.length;
}
let shown = false;                        // the view is up: the loop draws
const showProgress = () => {
  const share = shown ? count.done / count.total : count.nearDone / count.nearTotal;
  bar.style.width = `${(100 * share).toFixed(1)}%`;
  loadtext.textContent = `${shown ? 'Loading the city' : 'Loading the view'} ${Math.round(100 * share)}%`;
};
const tick = (near) => {
  count.done++;
  if (near) count.nearDone++;
  showProgress();
};

const groundLoaded = loader.loadAsync(TILES + index.ground).then((gltf) => {
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    const layer = o.material?.name;            // 06_tiles.py names each ground layer's material
    o.material = mat[layer] ?? mat.land;
    o.position.y += LAYER_Y[layer] ?? 0;       // (the node's own translation undoes the quantization)
    // the backdrop lies beyond the shadows' reach; the hills of the land, woods and airport cast theirs
    o.receiveShadow = layer !== 'backdrop';
    o.castShadow = layer === 'land' || layer === 'town' || layer === 'green' || layer === 'aeroway';
    // the water's mirror sees the ground from below: left out (the backdrop's far hills stay in)
    o.userData.noReflect = layer !== 'backdrop';
  });
  if (PROBE.lean) {
    const layers = [];
    gltf.scene.traverse((o) => { if (o.isMesh && o.material !== mat.backdrop) layers.push(o); });
    for (const o of layers) probeCells(o);
  }
  if (shadowTrim) {
    const layers = [];
    gltf.scene.traverse((o) => { if (o.isMesh && o.material !== mat.backdrop && !o.userData.probeCopy) layers.push(o); });
    for (const o of layers) shadowTrim.addGround(o);
  }
  mat.backdrop.userData.setTown(index.town?.rgb);   // the backdrop's towns carry on the town's roofscape
  // (its far mean colour; with block masses on it, the ground between them)
  mat.town.userData.setArea(index.extent, index.town?.rgb, index.tiles.some((t) => t.file.startsWith('m_')));
  scene.add(gltf.scene);
  // broadcast masts on the backdrop's hills (city.json masts, lattice.js): stood on whatever ground a ray
  // straight down meets there (the backdrop or the ground layers)
  if (city.masts?.length) {
    const ray = new THREE.Raycaster();
    const grounds = [];
    gltf.scene.traverse((o) => { if (o.isMesh && !o.userData.probeCopy) grounds.push(o); });
    gltf.scene.updateMatrixWorld(true);
    const groundAt = (x, z) => {
      ray.set(new THREE.Vector3(x, 5000, z), new THREE.Vector3(0, -1, 0));
      return ray.intersectObjects(grounds, false)[0]?.point.y ?? 0;
    };
    scene.add(createMasts(city.masts, mat.lattice, groundAt));
  }
  night.apply(gltf.scene);                     // lit ground after dark (night.js)
  shoreField(gltf.scene, index.extent);         // shore distance for the water colours
  performance.mark('ground in');
  tick(true);
  invalidate({ shadows: true });
});

// city.json masses.chunk (m, 0 = off, as New York and Shenzhen were measured): the town masses' big tiles (06e_masses'
// 12 km "L" tiles, one mesh each, never culled: half of it behind a street-level camera) cut at load into square
// chunks of this size, each a mesh of its own over the same vertex buffers, so frustum culling leaves out what the
// camera doesn't see: the same picture, fewer triangles. masses.aoCut: chunks wholly beyond occlusion's reach
// (AO_FAR m of view depth, where its fade has reached 1) are left out of its normals pre-pass. (?masschunk=ab keeps
// the uncut meshes too, hidden, for measuring: __viewer.massChunks.set(false) shows them instead)
const MASS_CHUNK = Number(params.get('masschunk')) || (params.get('masschunk') === '0' ? 0 : city.masses?.chunk ?? 0);
const MASS_AB = params.get('masschunk') === 'ab';
const MASS_AO_CUT = !!city.masses?.aoCut && params.get('massaocut') !== '0';
const AO_FAR = 6000;
const massChunks = [], massWhole = [], massAo = [];   // (massAo: every masses mesh with its world box, for aoCut)
function chunkMasses(root, size) {
  const meshes = [];
  root.traverse((o) => { if (o.isMesh && o.material?.name === 'masses' && o.geometry.index) meshes.push(o); });
  const v = new THREE.Vector3();
  for (const o of meshes) {
    const g = o.geometry, pos = g.attributes.position, idx = g.index.array, nf = g.index.count / 3;
    o.updateWorldMatrix(true, false);
    const wx = new Float32Array(pos.count), wz = new Float32Array(pos.count);
    let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
      wx[i] = v.x; wz[i] = v.z;
      x0 = Math.min(x0, v.x); x1 = Math.max(x1, v.x); z0 = Math.min(z0, v.z); z1 = Math.max(z1, v.z);
    }
    if (Math.max(x1 - x0, z1 - z0) <= 1.5 * size) continue;
    const nx = Math.ceil((x1 - x0) / size) || 1, nz = Math.ceil((z1 - z0) / size) || 1;
    const cellOf = new Int32Array(nf), counts = new Int32Array(nx * nz);
    for (let f = 0; f < nf; f++) {
      const a = idx[3 * f], b = idx[3 * f + 1], c = idx[3 * f + 2];
      const ix = Math.min(nx - 1, Math.floor(((wx[a] + wx[b] + wx[c]) / 3 - x0) / size));
      const iz = Math.min(nz - 1, Math.floor(((wz[a] + wz[b] + wz[c]) / 3 - z0) / size));
      counts[cellOf[f] = ix + nx * iz]++;
    }
    const outs = [...counts].map((n) => (n ? new idx.constructor(3 * n) : null)), fill = new Int32Array(nx * nz);
    for (let f = 0; f < nf; f++) {
      const k = cellOf[f], out = outs[k];
      out[fill[k]++] = idx[3 * f]; out[fill[k]++] = idx[3 * f + 1]; out[fill[k]++] = idx[3 * f + 2];
    }
    for (let k = 0; k < outs.length; k++) {
      const out = outs[k];
      if (!out) continue;
      const geo = new THREE.BufferGeometry();
      for (const [name, a] of Object.entries(g.attributes)) geo.setAttribute(name, a);
      geo.setIndex(new THREE.BufferAttribute(out, 1));
      // (bounds from the chunk's own vertices, in the mesh's local frame: computeBounding* would take every vertex)
      const box = new THREE.Box3();
      for (let i = 0; i < out.length; i++) box.expandByPoint(v.fromBufferAttribute(pos, out[i]));
      geo.boundingBox = box;
      geo.boundingSphere = box.getBoundingSphere(new THREE.Sphere());
      const chunk = new THREE.Mesh(geo, o.material);
      chunk.name = o.name;
      chunk.position.copy(o.position); chunk.quaternion.copy(o.quaternion); chunk.scale.copy(o.scale);
      o.parent.add(chunk);
      chunk.updateWorldMatrix(true, false);
      chunk.userData.massBox = box.clone().applyMatrix4(chunk.matrixWorld);
      massChunks.push(chunk);
      massAo.push(chunk);
    }
    if (MASS_AB) { o.visible = false; o.userData.massWhole = true; massWhole.push(o); } else o.removeFromParent();
  }
}

// city.json water.mirrorChunk (m, 0 = off) with water.mirrorCull: a building tile's facades mesh gets its triangles
// ordered by square cells of this size (the index rewritten in place: the same triangles, so every other pass draws
// it as before) and one mesh per cell over the same buffers (its own draw range), on a layer only the water's mirror
// draws, in place of the whole mesh: the mirror then leaves out each cell whose mirror image meets no water in view
// (water.js mirrorSeen). No buffer is copied
const MIRROR_CHUNK = city.water?.mirrorCull ? city.water?.mirrorChunk ?? 0 : 0;
function mirrorChunks(o, size) {
  const g = o.geometry, idx = g.index?.array, pos = g.attributes.position;
  if (!idx) return;
  o.updateWorldMatrix(true, false);
  const nf = idx.length / 3, v = new THREE.Vector3();
  const wx = new Float32Array(pos.count), wz = new Float32Array(pos.count);
  let x0 = Infinity, z0 = Infinity;
  if (!g.boundingSphere) g.computeBoundingSphere();
  if (!g.boundingBox) g.computeBoundingBox();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
    wx[i] = v.x; wz[i] = v.z; x0 = Math.min(x0, v.x); z0 = Math.min(z0, v.z);
  }
  // (cells in row order, so that neighbours along x follow one another in the index: a run of cells seen is one draw)
  const cellOf = new Int32Array(nf), counts = new Map();
  for (let f = 0; f < nf; f++) {
    const a = idx[3 * f], b = idx[3 * f + 1], c = idx[3 * f + 2];
    const k = Math.floor(((wx[a] + wx[b] + wx[c]) / 3 - x0) / size) + 1000 * Math.floor(((wz[a] + wz[b] + wz[c]) / 3 - z0) / size);
    cellOf[f] = k;
    counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  if (counts.size < 2) return;
  const keys = [...counts.keys()].sort((a, b) => a - b);
  const start = new Map();
  let o3 = 0;
  for (const k of keys) { start.set(k, o3); o3 += 3 * counts.get(k); }
  const out = new idx.constructor(idx.length), fill = new Map(start);
  for (let f = 0; f < nf; f++) {
    const k = cellOf[f]; let p = fill.get(k);
    out[p++] = idx[3 * f]; out[p++] = idx[3 * f + 1]; out[p++] = idx[3 * f + 2];
    fill.set(k, p);
  }
  idx.set(out);
  o.updateWorldMatrix(true, false);
  const cells = keys.map((k) => {
    const s0 = start.get(k), n = 3 * counts.get(k), box = new THREE.Box3();
    for (let i = s0; i < s0 + n; i++) box.expandByPoint(v.fromBufferAttribute(pos, idx[i]));
    return { start: s0, count: n, box: box.applyMatrix4(o.matrixWorld) };
  });
  // at most MIRROR_RUNS draws per mesh in the mirror: meshes over the same buffers, their draw ranges set per mirror pass
  const meshes = [];
  for (let r = 0; r < MIRROR_RUNS; r++) {
    const geo = new THREE.BufferGeometry();
    for (const [name, a] of Object.entries(g.attributes)) geo.setAttribute(name, a);
    geo.setIndex(g.index);
    geo.boundingSphere = g.boundingSphere ?? (g.computeBoundingSphere(), g.boundingSphere);
    geo.boundingBox = g.boundingBox;
    const m = new THREE.Mesh(geo, o.material);
    m.name = `${o.name}-mirror`;
    m.position.copy(o.position); m.quaternion.copy(o.quaternion); m.scale.copy(o.scale);
    m.layers.set(MIRROR_LAYER);
    m.castShadow = false;
    m.receiveShadow = true;
    m.visible = false;
    m.userData.mirrorRun = true;
    o.parent.add(m);
    meshes.push(m);
  }
  o.userData.mirrorRuns = { cells, meshes };
}
const MIRROR_RUNS = 2;

// facade.probe.glassOnly: how much glass a tile's facades mesh holds (m² of wall in the glass styles: curtain walls, fins,
// bands, signs, patterned skins; landmark rows carry these styles too) and the box round it, from its arrays as it arrives
const GLASS_IDS = new Set(['glass', 'fins', 'bands', 'piers', 'signs', 'lattice', 'honeycomb', 'panel']
  .map((n) => index.styles.indexOf(n)).filter((i) => i >= 0));
const glassA = new THREE.Vector3(), glassB = new THREE.Vector3(), glassC = new THREE.Vector3();
function glassIn(root, o) {
  const g = o.geometry, uv1 = g.attributes.uv1, pos = g.attributes.position, nrm = g.attributes.normal;
  if (!uv1 || !pos || !GLASS_IDS.size) return;
  const facK = index.uvRange.fac[0], n = pos.count, idx = g.index?.array;
  const isGlass = new Uint8Array(n);
  let any = false;
  for (let i = 0; i < n; i++) if (GLASS_IDS.has(Math.floor(uv1.getX(i) * facK + 0.0005)) && !(nrm && Math.abs(nrm.getY(i)) > 0.9)) { isGlass[i] = 1; any = true; }
  if (!any) return;
  o.updateWorldMatrix(true, false);
  const info = (root.userData.glass ??= { area: 0, box: new THREE.Box3() });
  const nf = idx ? idx.length / 3 : n / 3;
  for (let f = 0; f < nf; f++) {
    const a = idx ? idx[3 * f] : 3 * f, b = idx ? idx[3 * f + 1] : 3 * f + 1, c = idx ? idx[3 * f + 2] : 3 * f + 2;
    if (!isGlass[a]) continue;
    glassA.fromBufferAttribute(pos, a).applyMatrix4(o.matrixWorld);
    glassB.fromBufferAttribute(pos, b).applyMatrix4(o.matrixWorld);
    glassC.fromBufferAttribute(pos, c).applyMatrix4(o.matrixWorld);
    info.box.expandByPoint(glassA).expandByPoint(glassB).expandByPoint(glassC);
    glassB.sub(glassA); glassC.sub(glassA);
    info.area += glassB.cross(glassC).length() / 2;
  }
}
// whether glass worth a capture is in the view: the glass of the tiles shown whose glass box is in the camera's frustum
// and within glassNear metres of the probe (its nearest point), each tile's wall area seen at its box's nearest point
// (at least 50 m) from the camera and a third of it facing the camera, covers glassShare of the screen's pixels or more:
// a generous estimate (over 1 among towers), meant to err towards capturing. Paris: La Défense 1.07, the BnF 0.1, the
// Latin Quarter 0.0018 (Jussieu's tower and the Institut du Monde arabe, which mirror a dark city with a capture and the
// pale sky map without one: the threshold 0.0003 keeps their capture), the overview 0.0006, the Marais 0. London and
// Berlin have glass-style walls in nearly every view (Westminster 0.6, Kreuzberg 0.05: Berlin's scattered glass offices
// turn pale without a capture), so there the capture is rarely skipped and `lean` is what lightens it
const glassFrustum = new THREE.Frustum(), glassM = new THREE.Matrix4(), glassP = new THREE.Vector3();
function glassInView(detail = false) {
  camera.updateMatrixWorld();
  glassFrustum.setFromProjectionMatrix(glassM.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse),
    camera.coordinateSystem, camera.reversedDepth);
  cityReflection.positionFor(controls.target, terrain.height(controls.target.x, controls.target.z), glassP);
  const c = camera.position, focal = 1 / Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);   // (per half screen height)
  let share = 0;
  for (const g of tileGroups) {
    const gl = g.userData.glass;
    if (!gl || !g.visible) continue;
    const b = gl.box;
    if (Math.hypot(Math.max(b.min.x - glassP.x, 0, glassP.x - b.max.x), Math.max(b.min.z - glassP.z, 0, glassP.z - b.max.z)) > PROBE.glassNear) continue;
    if (!glassFrustum.intersectsBox(b)) continue;
    const d = Math.max(50, Math.hypot(Math.max(b.min.x - c.x, 0, c.x - b.max.x), Math.max(b.min.y - c.y, 0, c.y - b.max.y),
      Math.max(b.min.z - c.z, 0, c.z - b.max.z)));
    // (the screen is 2 x 2 aspect units of half heights: a share of (focal / d)^2 m^-2 over 4 aspect)
    share += (gl.area / 3) * (focal / d) ** 2 / (4 * camera.aspect);
    if (share >= PROBE.glassShare && !detail) return true;
  }
  return detail ? share : false;
}

// a building tile (buildings, road and bridge meshes) or a markings tile into the scene; both are culled by
// distance (cullTiles), markings tiles also with the menu's switch
function addTile(kind, t, root) {
  if (MASS_CHUNK > 0 && kind === 'tiles' && t?.file?.startsWith('m_')) chunkMasses(root, MASS_CHUNK);
  root.traverse((o) => {
    if (!o.isMesh) return;
    if (kind === 'markings') {
      // flat on the roads: they receive shadows but cast none, and the water's mirror leaves them out (seen
      // from below)
      o.material = mat.markings;
      o.castShadow = false;
      o.userData.noReflect = true;
    } else {
      const k = o.material?.name;              // buildings, road or bridge (06_tiles.py); masses (06e_masses.py)
      o.material = k === 'masses_small' ? mat.masses : mat[k] ?? mat.buildings;
      if (k === 'masses_small') root.userData.small = o;   // houses: drawn only near (cullTiles)
      if (k?.startsWith('masses')) root.userData.masses = true;   // (the menu's Towns switch)
      // roads lying on the ground can't cast a visible shadow; a lattice's cut-out panels would cast solid sheets
      // (its solid members, in the buildings mesh, cast the structure's shadow)
      o.castShadow = k !== 'road' && k !== 'lattice' && !k?.startsWith('masses');   // (the town masses: none, for speed)
      if (k?.startsWith('masses')) o.userData.noReflect = true;
      if (MASS_AO_CUT && k?.startsWith('masses') && !o.userData.massBox) { o.userData.massBox = new THREE.Box3().setFromObject(o); massAo.push(o); }
      if (k === 'road') o.userData.noReflect = true;   // nor show in the water's mirror (seen from below)
      // bridge meshes without cables have no uv; the bridge material reads it (the necklace lights)
      if (k === 'bridge' && !o.geometry.attributes.uv) {
        o.geometry.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(o.geometry.attributes.position.count * 2), 2));
      }
    }
    o.receiveShadow = true;
    if (o.userData.massWhole) return;          // (masses.chunk's A/B: the uncut mesh, hidden, kept as it is)
    if (PROBE.glassOnly && kind === 'tiles' && o.material === mat.buildings) glassIn(root, o);
    // (a building tile's facades mesh: its parapets are made from its arrays before they are dropped)
    if (t?.file && o.geometry.attributes.uv1) o.geometry.userData.parapetsOf = t.file;
    toFree.push(o.geometry);
  });
  if (MIRROR_CHUNK > 0 && kind === 'tiles') {
    const facades = [];
    root.traverse((o) => { if (o.isMesh && o.material === mat.buildings) facades.push(o); });
    for (const o of facades) mirrorChunks(o, MIRROR_CHUNK);
  }
  root.userData.tile = t;
  root.userData.markings = kind === 'markings';
  if (shadowTrim && kind === 'tiles') shadowTrim.addTile(root);
  tileGroups.push(root);
  scene.add(root);
  night.apply(root);
  invalidate({ shadows: kind === 'tiles', redraw: true });
}
// once a tile's buffers are on the GPU, its arrays in the page's memory are dropped (about 190 MB in New York):
// the renderer never reads them again, as nothing changes them. Each is swapped for an empty array of the same
// type (the vertex formats and shaderKind read the type; the counts are kept). three's onUpload hook would do
// this, but r186's WebGPURenderer never calls it. Bounds are worked out first (frustum culling needs them).
const toFree = [];
// (?keeparrays=1, opt-in: the arrays are kept, so a script can read the geometry: scripts/flythrough.mjs builds a
// height grid from it for its clearance and label-occlusion checks)
const KEEP_ARRAYS = params.get('keeparrays') === '1';
// (a building tile's rooftop parapets are made from its arrays first, for at most PARAPETS_MS a frame; the rest
// wait for the next frame)
const PARAPETS_MS = 8;
function freeUploaded() {
  const uploaded = (a) => renderer.backend.has(a.isInterleavedBufferAttribute ? a.data : a);
  const t0 = performance.now();
  for (let i = toFree.length - 1; i >= 0; i--) {
    const g = toFree[i], attrs = Object.values(g.attributes);
    if (g.index && !uploaded(g.index) || !attrs.every(uploaded)) continue;
    if (g.userData.parapetsOf && rooftops) {
      if (performance.now() - t0 > PARAPETS_MS || !rooftops.prepareParapets(g.userData.parapetsOf)) continue;
    }
    if (!g.boundingSphere) g.computeBoundingSphere();
    if (!g.boundingBox) g.computeBoundingBox();
    for (const a of [g.index, ...attrs]) {
      const b = a?.isInterleavedBufferAttribute ? a.data : a;
      if (b?.array.length && !KEEP_ARRAYS) b.array = new b.array.constructor(0);
    }
    toFree.splice(i, 1);
  }
}
async function gunzip(buf) {
  const b = new Uint8Array(buf);
  if (b[0] !== 0x1f || b[1] !== 0x8b) return buf;     // a server may already have decoded it
  return new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
}
// city.json tiles.merge: the layers whose meshes are merged across a block's tiles, one mesh per layer and block
// (e.g. ["road", "bridge", "markings"]: in Paris 542 of the overview's ~870 draws were those three, a few
// thousand triangles each). A block is culled as one tile then; the buildings stay per tile (the rooftops' parapets
// are made from each tile's own). Positions become 32-bit floats in world metres (each tile's are 16-bit, scaled
// and placed by its node), the other attributes are copied as they are (the same formats in every tile)
const MERGE = new Set(params.get('merge') === '0' ? [] : city.tiles.merge);
function mergeMeshes(meshes) {
  const out = new THREE.BufferGeometry();
  // (every attribute any of them has; zeros where one lacks it: a bridge without cables has no uv)
  const names = [...new Set(meshes.flatMap((m) => Object.keys(m.geometry.attributes)))];
  let nv = 0, ni = 0;
  for (const m of meshes) { nv += m.geometry.attributes.position.count; ni += m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count; }
  const index = new Uint32Array(ni), v = new THREE.Vector3();
  for (const k of names) {
    const a = meshes.find((m) => m.geometry.attributes[k]).geometry.attributes[k];
    const array = k === 'position' ? new Float32Array(nv * 3) : new a.array.constructor(nv * a.itemSize);
    let o = 0;
    for (const m of meshes) {
      const src = m.geometry.attributes[k];
      if (!src) { o += m.geometry.attributes.position.count * a.itemSize; continue; }
      if (k === 'position') {
        m.updateWorldMatrix(true, false);
        for (let i = 0; i < src.count; i++, o += 3) v.fromBufferAttribute(src, i).applyMatrix4(m.matrixWorld).toArray(array, o);
      } else if (src.isInterleavedBufferAttribute) {
        // (the stored values, not getComponent's: that would scale a normalized one to -1..1)
        const { array: d, stride } = src.data;
        for (let i = 0; i < src.count; i++, o += src.itemSize) for (let c = 0; c < src.itemSize; c++) array[o + c] = d[i * stride + src.offset + c];
      } else { array.set(src.array.subarray(0, src.count * src.itemSize), o); o += src.count * src.itemSize; }
    }
    out.setAttribute(k, new THREE.BufferAttribute(array, k === 'position' ? 3 : a.itemSize, k === 'position' ? false : a.normalized));
  }
  let base = 0, o = 0;
  for (const m of meshes) {
    const g = m.geometry, n = g.attributes.position.count;
    if (g.index) for (let i = 0; i < g.index.count; i++) index[o++] = g.index.getX(i) + base;
    else for (let i = 0; i < n; i++) index[o++] = i + base;
    base += n;
  }
  out.setIndex(new THREE.BufferAttribute(index, 1));
  out.computeBoundingSphere();
  out.computeBoundingBox();
  return out;
}
// the meshes of the MERGE layers among a block's parsed parts taken out and merged, a group per layer (a
// building tile's mesh of that layer removed from its tile), added as tiles covering the whole block
function mergeBlock(b, parsed) {
  const byLayer = new Map();
  for (const { kind, root } of parsed) {
    root.traverse((o) => {
      if (!o.isMesh) return;
      const layer = kind === 'markings' ? 'markings' : o.material?.name;
      if (!MERGE.has(layer)) return;
      if (!byLayer.has(layer)) byLayer.set(layer, []);
      byLayer.get(layer).push(o);
    });
  }
  for (const [layer, meshes] of byLayer) {
    for (const m of meshes) m.removeFromParent();
    const mesh = new THREE.Mesh(mergeMeshes(meshes), meshes[0].material);
    mesh.name = layer;
    for (const m of meshes) m.geometry.dispose();
    const root = new THREE.Group();
    root.add(mesh);
    addTile(layer === 'markings' ? 'markings' : 'tiles', { x: b.x, z: b.z, size: b.size, merged: layer }, root);
  }
}
async function loadBlock(b) {
  let added = 0;
  try {
    const r = await fetch(b.url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    let buf = await r.arrayBuffer();
    if (b.gzip) buf = await gunzip(buf);
    const parsed = [];
    for (const p of b.parts) {
      const gltf = await loader.parseAsync(p.offset === undefined ? buf : buf.slice(p.offset, p.offset + p.length), '');
      parsed.push({ kind: p.kind, file: p.file, root: gltf.scene });
    }
    if (MERGE.size) mergeBlock(b, parsed);
    // (a tile left empty by the merge is added all the same: the rooftops wait for every tile's group)
    for (const { kind, file, root } of parsed) {
      addTile(kind, tileInfo[kind].get(file), root);
      tick(b.near);
      added++;
    }
  } catch (e) {
    console.warn('city: block failed', b.url, e);
    for (; added < b.parts.length; added++) tick(b.near);
  }
}
// BLOCK_CONCURRENCY blocks at a time, the next always the one nearest the orbit target (the start view's until
// the view shows). cityLoaded: all are in; nearLoaded: those within NEAR of the start view are
const BLOCK_CONCURRENCY = 4;
let nearLeft = blocks.filter((b) => b.near).length, nearIn;
const nearLoaded = new Promise((resolve) => { nearIn = resolve; });
if (!nearLeft) nearIn();
let pumpBlocks = () => {};
const cityLoaded = new Promise((resolve) => {
  const queue = blocks.slice();
  let inflight = 0;
  const pump = pumpBlocks = () => {
    if (!queue.length && !inflight) resolve();
    while (inflight < BLOCK_CONCURRENCY && queue.length) {
      const focus = shown ? controls.target : startView;
      // (until the view shows, the blocks it waits for first: with loading.frustumNear some near ones don't count)
      const rank = (b) => blockDistance(b, focus) + (b.late ? 1e9 : 0) + (shown || b.near ? 0 : 1e8);
      let k = 0;
      for (let i = 1; i < queue.length; i++) if (rank(queue[i]) < rank(queue[k])) k = i;
      if (queue[k].late && !shown) break;
      const b = queue.splice(k, 1)[0];
      inflight++;
      loadBlock(b).then(() => {
        inflight--;
        if (b.near && --nearLeft === 0) nearIn();
        pump();
      });
    }
  };
  pump();
});

const terrain = await terrainLoaded;
// trees (08_trees.py): web/trees links to ../../data/<city>/trees
const trees = await createTrees({ scene, camera, invalidate, renderer, terrain, classes: city.trees.classes, species: city.trees.species, dense: city.trees.dense, far: city.trees.far, streetLift: city.trees.streetLift ?? 0, trunkDrop: city.trees.trunkDrop ?? 0, carpetBranch: city.trees.carpetBranch ?? false, carpetNormals: city.trees.carpetNormals ?? false, carpetBlend: city.trees.carpetBlend ?? null,
  // (trees.uplight, opt-in: Singapore M8 fix round 1)
  uplight: city.trees.uplight ? { ...city.trees.uplight, lights: night.u.lampLights } : null });
// (city.json trees.near, opt-in: m within which trees are drawn as full models, the impostors beyond; a number, or
// { webgpu, webgl } per backend; unset: trees.js's 280 m. Singapore M6 fix round: the parks' and avenues' big crowns)
{
  const tn = city.trees?.near;
  const d = typeof tn === 'number' ? tn : tn?.[renderer.backend.isWebGLBackend ? 'webgl' : 'webgpu'];
  if (d) trees.setNear(d);
}
// tanks, stair boxes, parapets, sheds, solar panels... on the roofs (06c_rooftops.py; web/rooftops links to
// ../../data/<city>/rooftops). Parapets are built from the loaded building tiles. null without the folder
const rooftops = await createRooftops({ scene, camera, invalidate, tileGroups, tilesIndex: index, terrain, look: city.rooftopLook ?? {},
  styles: facadeStyles.styles, night: night.u });
if (rooftops) rooftops.group.visible = settings.rooftops;
// traffic and parked cars (06d_cars.py; web/cars links to ../../data/<city>/cars); none if it is missing
const cars = await createCars({ scene, camera, invalidate, envMap, terrain, night: night.u, sunShade: city.cars?.sunShade, glass: city.cars?.glass,
  shadowFade: city.cars?.shadowFade, posts: city.cars?.posts ?? false, keepOut: city.cars?.keepOut ?? 0 });
cars.group.visible = settings.traffic;
performance.mark('layers');

// ---------------------------------------------------------------- views
// (a jump to a chosen view recaptures glass's city probe for its first frame, not only once it settles: the
// first frames reflected the place left behind, the WTC's blue carried to the next view or another view's dark
// to the WTC, and the glass jumped a quarter of a second later; the same one capture, only earlier)
let probeJump = false;
function goTo(v) {
  probeJump = true;
  controls.target.set(v.x, v.y ?? terrain.height(v.x, v.z), v.z);
  // stand on the afternoon sun's side of the target (city.json's camera.azimuth; by default south-south-west
  // north of the equator) so the sun lights the facades we see; a view may name its own direction
  camera.position.copy(controls.target).addScaledVector(compass(v.azimuth ?? city.camera.azimuth, v.elevation), v.distance);
  controls.update();
  lastTarget.copy(controls.target);            // a chosen view keeps its target's height (a landmark's third)
  settling = false;
  invalidate({ shadows: true });
}
// ---------------------------------------------------------------- the ground under the view
// Panning slides the orbit target across the map at its own height, which over the hills would bury it or
// leave it hanging over a valley: once it has been panned, the target (and the camera with it, so the view
// only shifts) eases back onto the ground under it. A target lifted well off the ground (a chosen view aims
// part of the way up a landmark, or at an eye line) goes instead down the line of sight onto the ground, the
// camera staying where it is, so the view doesn't change: eased down with the camera, the view sank by up to
// a few hundred metres in the first frames of a drag after choosing a view, and lurched before following the
// pointer. The camera keeps CAMERA_CLEAR m above the highest ground within a few metres (city.json camera.clear;
// London's street-level views at eye height: 2). A handful of TIN lookups on frames that are drawn anyway.
const CAMERA_CLEAR = city.camera.clear ?? 10, LIFTED = 25, LIFTED_REACH = 20000;
const lastTarget = new THREE.Vector3();
let settling = false;
function followGround() {
  const t = controls.target, c = camera.position;
  let changed = false;
  if (Math.abs(t.x - lastTarget.x) + Math.abs(t.z - lastTarget.z) > 0.01) settling = true;
  lastTarget.copy(t);
  if (settling && t.y - terrain.height(t.x, t.z) > LIFTED && c.y > t.y + 1) {
    // where the line of sight meets the ground: a few steps, the ground's height read again at each estimate
    const drop = c.y - t.y;
    let s = (c.y - terrain.height(t.x, t.z)) / drop;
    for (let i = 0; i < 4; i++) s = (c.y - terrain.height(c.x + (t.x - c.x) * s, c.z + (t.z - c.z) * s)) / drop;
    if (s > 1 && s * Math.hypot(t.x - c.x, t.z - c.z) < LIFTED_REACH) {
      t.set(c.x + (t.x - c.x) * s, c.y - drop * s, c.z + (t.z - c.z) * s);
      lastTarget.copy(t);
      changed = true;
    }
  }
  if (settling) {
    const dy = terrain.height(t.x, t.z) - t.y;
    const step = Math.abs(dy) < 0.05 ? dy : dy * 0.3;
    t.y += step; c.y += step;
    settling = Math.abs(dy) >= 0.05;
    changed = step !== 0;
  }
  const floor = terrain.ceiling(c.x, c.z, 15) + CAMERA_CLEAR;
  if (c.y < floor) { c.y = floor; changed = true; }
  return changed;
}

goTo(startView);
trees.group.visible = feature('trees', 'trees');   // ?trees=0: off

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  invalidate();
});

// ---------------------------------------------------------------- trackpad gestures
// Trackpad mode: two-finger scroll orbits (sideways turns, up/down tilts), pinch zooms, shift +
// two-finger scroll pans; a mouse wheel still zooms. Mouse mode: the wheel zooms. Click-drag always pans;
// shift/cmd-drag rotates.

const spherical = new THREE.Spherical();
const offset = new THREE.Vector3();
// A mouse wheel keeps zooming in trackpad mode. Each burst of wheel events (a gap of over 250 ms starts a new
// one) is judged by its first event and keeps that verdict, so a fast two-finger swipe can't flip mid-gesture:
// a mouse wheel scrolls by lines (deltaMode 1, Firefox) or by whole notches (a step of 50 px or more, ~100-120
// in Chrome, nothing sideways); a trackpad's gesture starts with a small or sideways pixel delta. (wheelDeltaY is
// not used: Chrome over CDP reports -119 for every event, and fractional device scales round it the same way.)
let wheelBurstAt = -Infinity, wheelIsMouse = false;
const mouseWheel = (e) => {
  if (e.timeStamp - wheelBurstAt > 250) {
    wheelIsMouse = e.deltaMode !== 0
      || (e.deltaX === 0 && Math.abs(e.deltaY) >= 50);
  }
  wheelBurstAt = e.timeStamp;
  return wheelIsMouse;
};
renderer.domElement.addEventListener('wheel', (e) => {
  if (!settings.trackpad || e.ctrlKey) return;          // pinch arrives as ctrl+wheel: let the controls zoom
  if (mouseWheel(e)) return;                              // a mouse wheel zooms, as in mouse mode
  e.preventDefault();
  e.stopImmediatePropagation();
  offset.copy(camera.position).sub(controls.target);
  if (e.shiftKey) {                                       // pan along the ground, scaled to the view distance
    const k = offset.length() * 0.0015;
    const right = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0).setY(0).normalize();
    const fwd = new THREE.Vector3(-right.z, 0, right.x);
    const move = right.multiplyScalar(e.deltaX * k).add(fwd.multiplyScalar(-e.deltaY * k));
    controls.target.add(move);
    camera.position.add(move);
  } else {
    spherical.setFromVector3(offset);
    // directions chosen to match macOS natural scrolling as used in practice (reversed after testing)
    spherical.theta += e.deltaX * 0.004;
    spherical.phi = THREE.MathUtils.clamp(spherical.phi + e.deltaY * 0.003, 0.05, controls.maxPolarAngle);
    camera.position.copy(controls.target).add(offset.setFromSpherical(spherical));
    camera.lookAt(controls.target);
  }
  controls.update();
  invalidate();
}, { capture: true, passive: false });

// ---------------------------------------------------------------- ambient occlusion (settled frames)
// A normals pre-pass feeds screen-space AO, which darkens only the sky/ambient light, so alleys,
// courtyards and the feet of buildings get the soft occlusion the sun's shadows alone don't give.
// It costs two scene passes plus the AO, so it runs only on the frame drawn once the view settles.
const pipeline = new THREE.RenderPipeline(renderer);
const prePass = pass(scene, camera);
prePass.transparent = false;
prePass.setMRT(mrt({ output: packNormalToRGB(normalView) }));
prePass.getTexture('output').type = THREE.UnsignedByteType;
const prePassNormal = sample((uv) => unpackRGBToNormal(prePass.getTextureNode().sample(uv)));
const aoPass = ssao(prePass.getTextureNode('depth'), prePassNormal, camera);
aoPass.radius.value = 18;              // metres
aoPass.intensity.value = 3;
aoPass.resolutionScale = 0.5;
// The pre-pass and the SSAO draw under the renderer's own context node, whoever asks for them first. Each runs once a
// frame (updateBefore) for the first node that needs it: a mesh of the scene pass (below), while that pass has put its
// own context (the occlusion) on the renderer, or the pipeline's output quad, under the renderer's. A render object's
// cache key includes renderer.contextNode's id, so each switch between the two made the SSAO's quads (SSAO.AO and
// SSAO.Blur) and the pre-pass's objects anew and relinked their programs. A frame always asked from the scene pass,
// but a warm-up round stops wherever its budget runs out, often before the scene pass prepared anything: the same
// two SSAO programs linked again and again, 40-55 % of New York's warm-up links on WebGL 2 (the same pixels either
// way: the pre-pass writes normals and depth, the SSAO quads light nothing). And the SSAO's (and the bloom's, below)
// quads are set up once: three's SSAONode.setup runs again for every material built that samples the occlusion (each
// scene-pass material in each pass and light), and each time gave its quads' materials new fragment nodes and
// needsUpdate, a new program cache key: both programs dropped and linked again after nearly every warm-up round that
// built something (Berlin: 200 of the warm-up's 426 links). Later setups now return what the first one made
const setupOnce = (node) => {
  const setup = node.setup;
  let made = null;
  node.setup = function (builder) { return (made ??= setup.call(this, builder)); };
};
setupOnce(aoPass);
const baseContext = renderer.contextNode;
for (const node of [prePass, aoPass]) {
  const update = node.updateBefore;
  node.updateBefore = function (...a) {
    const was = renderer.contextNode;
    renderer.contextNode = baseContext;
    try { return update.apply(this, a); } finally { renderer.contextNode = was; }
  };
}
const scenePass = pass(scene, camera, { samples: 4 });
// occlusion fades out between 3 and 6 km: screen-space AO has nothing to find that far away, only depth
// precision to trip over (it drew horizontal bands across distant views)
// (the pre-pass depth, logarithmic or reversed, is converted back to view distance first)
const aoDepthRaw = prePass.getTextureNode('depth').sample(screenUV).r;
// The depth is converted with the scene camera's own near and far. This node runs in the pipeline's output pass, where
// cameraNear and cameraFar are the full-screen quad's orthographic camera's (0 and 1), not the view's: the distance came
// out 0 and the far fade never took the occlusion away, so its depth noise drew faint vertical streaks over Hong Kong's
// hills and evenly spaced horizontal stripes across the haze over Fuji (Known issue 79; measured: both vanish with the
// occlusion's intensity at 0). Found twice as an opt-in (ao.cameraDepth, Hong Kong M7f; ao.sceneCamera, Tokyo M7), the
// default for every city since 8 Oct 2026 (before/after in plans/2026-10-08-final-checks.md). Opt-out, the old
// unfaded occlusion: city.json ao.cameraDepth false, or ?aofix=0 (?aofix=1 forces it on)
const AO_SCENE = params.has('aofix') ? params.get('aofix') !== '0'
  : city.ao?.cameraDepth !== false && city.ao?.sceneCamera !== false;
const AO_CAM_NEAR = AO_SCENE ? reference('near', 'float', camera) : cameraNear;
const AO_CAM_FAR = AO_SCENE ? reference('far', 'float', camera) : cameraFar;
const aoDepth = (renderer.logarithmicDepthBuffer ? logarithmicDepthToViewZ(aoDepthRaw, AO_CAM_NEAR, AO_CAM_FAR)
  : perspectiveDepthToViewZ(aoDepthRaw, AO_CAM_NEAR, AO_CAM_FAR)).negate();
// (city.json ao.far [from, to] m, opt-in, default [3000, 6000]: Hong Kong M7, the occlusion's faint vertical streaks
// over the hills 3-6 km out from the harbour views, where its 18 m radius finds only depth noise on the slopes)
const AO_FADE = city.ao?.far ?? [3000, 6000];
const aoFar = smoothstep(float(AO_FADE[0]), float(AO_FADE[1]), aoDepth);
// (the sky writes no depth: the cleared value, 1 with the log buffer, 0 reversed. SSAO skips only depth 1, so with reversed
// depth the sky's pixels got an occlusion of their own, a faint seam across the sky: none there)
const aoSky = renderer.reversedDepthBuffer ? aoDepthRaw.lessThanEqual(0) : aoDepthRaw.greaterThanEqual(1);
const aoTex = select(aoSky, float(1), mix(aoPass.getTextureNode().sample(screenUV).r, float(1), aoFar));
// inside the scene's materials the fade takes the fragment's own distance, not the pre-pass depth: a material
// sampling that depth texture made it a binding in passes where it is also the attachment (the pre-pass, the
// shadow and probe passes compiled with the same context), and WebGPU's validation error then failed whichever
// pipelines three was creating at that moment: cars, facades or shadows went missing at random
const aoScene = mix(aoPass.getTextureNode().sample(screenUV).r, float(1), smoothstep(float(AO_FADE[0]), float(AO_FADE[1]), positionView.z.negate()));
scenePass.contextNode = builtinAOContext(aoScene);
// A render context of its own for this pass (an MRT of just its colour: the same output, another key). three keeps one
// render object per mesh, material, render context and lights, and r186's RenderContexts key a context by the
// target's format, type and samples, its MRT and the call depth, not by the target: this pass and the glow's still
// pass (stillGlow, below: 4 samples, the same format, no MRT) shared one, so their render objects were the same. But
// this pass draws with its own contextNode (the occlusion above), which is part of a render object's cache key
// (renderer.contextNode's id): each time a frame used the other of the two, three found every render object of the
// view stale and made it again. After dark at a far view (the moving frames through this pass until the moving glow
// is ready, the settled ones through stillGlow) that was ~400 objects at once, a 10-15 s freeze at a night start at
// Paris's overview (M9 round 3; see also the dispose guard below)
scenePass.setMRT(mrt({ output }));
// the sky light is weak next to the sun, so occlusion also darkens the final image a little: contact
// shadows then read under direct light too (not physical, the usual artistic compromise)
pipeline.outputNode = vec4(scenePass.rgb.mul(mix(float(1), aoTex, float(0.45))), scenePass.a);
// ?reflect-water=0 or the menu's Mirror switch: no mirrored city in the water (one scene pass less per frame)
settings.mirror = feature('reflect-water', 'mirror');
setWaterReflection(settings.mirror);

// ---------------------------------------------------------------- glow after dark
// Lit windows, signs, street lamps and headlights glow a little (BloomNode: what is brighter than the
// threshold, blurred at five scales and added back), only while the city's lights are on. Settled frames
// then go through a copy of the occlusion pipeline that adds it (sharing its passes); frames drawn without
// occlusion through a pipeline of one scene pass and its bloom instead of the plain render, so they don't
// lose it: multisampled for still frames (animation, far views), not while the view moves (a quarter-size
// bloom too), which is then cheaper than the plain multisampled render. The bloom works from half size (a
// quarter while moving): a soft halo needs no more, and it is cheaper. (Switching pipelines, not one
// pipeline's output: rebuilding that recompiled the bloom's shaders, over a second each time.) By day
// neither bloom runs and nothing changes. ?glow=0 or the menu's Glow switch: off.
settings.glow = feature('glow', 'glow');
const GLOW = { strength: 0.45, radius: 0.6, threshold: 0.7 };
// The bloom's bright pass reads a non-finite channel (NaN, +-Inf) as 0, otherwise exactly three's luminosity high pass.
// A few NaN pixels in the occlusion pass's colour after dark (Shenzhen's Futian at 21:00: 6-130 of 6.4 M, on the
// ground near the towers, only with Occlusion on) went through the blur and the mip chain into a NaN over most of
// the blur targets: settled night frames showed black screen-space rectangles a quarter to half the view across
// (Singapore REPORT M8). A NaN pixel itself stays a black dot, as before. (A bit test: the shader compilers may
// assume finite floats and fold x != x away)
// (city.json glow.max, opt-in (Hong Kong M8): each channel the bright pass reads capped at that (linear): a few finite but
// huge pixels (a specular spike) blurred through the mip chain into a glow ball a fifth of the view across, its colour
// changing from frame to frame (Known issue 77's "cyan glow point" in Shenzhen, Hong Kong's harbourfront at 21:00))
const GLOW_MAX = city.glow?.max ?? null;
const finiteHighPass = Fn(({ input, threshold, smoothWidth }) => {
  let c = vec4(finiteChannel(input.r), finiteChannel(input.g), finiteChannel(input.b), finiteChannel(input.a));
  if (GLOW_MAX != null) c = c.min(vec4(GLOW_MAX, GLOW_MAX, GLOW_MAX, GLOW_MAX));
  return mix(vec4(0), c, smoothstep(threshold, threshold.add(smoothWidth), luminance(c.rgb)));
});
const settledBloom = bloom(scenePass.getTextureNode(), GLOW.strength, GLOW.radius, GLOW.threshold);
settledBloom.highPassFn = finiteHighPass;
settledBloom.setResolutionScale(0.5);
setupOnce(settledBloom);                  // (its setup pushed five more blur materials and relinked its programs each time)
const settledGlow = new THREE.RenderPipeline(renderer);
settledGlow.outputNode = vec4(pipeline.outputNode.rgb.add(settledBloom.rgb), pipeline.outputNode.a);
function glowPipeline(samples, scale) {
  const p = new THREE.RenderPipeline(renderer);
  const colour = pass(scene, camera, { samples });
  p.bloom = bloom(colour.getTextureNode(), GLOW.strength, GLOW.radius, GLOW.threshold);
  p.bloom.highPassFn = finiteHighPass;
  p.bloom.setResolutionScale(scale);
  setupOnce(p.bloom);
  p.outputNode = vec4(colour.rgb.add(p.bloom.rgb), colour.a);
  return p;
}
const stillGlow = glowPipeline(4, 0.5), movingGlow = glowPipeline(0, 0.25);
let glowing = false;
let warmLight = null;                      // (the light a warm-up step prepares, while it runs: see warmStep)
// before each frame: glow on or off with the lights, its strength
function updateGlow() {
  glowing = settings.glow && (warmLight ? warmLight !== 'day' : night.state.lights > 0.02);
  settledBloom.strength.value = stillGlow.bloom.strength.value = movingGlow.bloom.strength.value = GLOW.strength * night.state.lights;
}
// a settled frame (with occlusion), and a frame without: each with the glow while it is on
const renderSettled = () => (glowing ? settledGlow : pipeline).render();
const renderPlain = () => (glowing ? (moving ? movingGlow : stillGlow).render() : renderer.render(scene, camera));
// ---------------------------------------------------------------- shaders without stalls
// A node material is built (TSL to WGSL or GLSL) and its pipeline compiled the first time a pass draws it,
// which stalls that frame: some 30-90 ms of script per material and pass, then the driver's compiler (the
// facades' shaders alone keep it busy for a second), for a dozen materials in each of five passes. So objects
// are prepared ahead where possible and never waited for:
// - compileOnly(draw, budget) runs draw() with the renderer drawing nothing (no pass begun, no target
//   touched): each object only has its node material built for the pass it is in (the render target, MRT,
//   context and lights a real frame gives it, so the same cache keys) and its pipeline created asynchronously
//   (WebGPU's createRenderPipelineAsync, WebGL's KHR_parallel_shader_compile), so neither the main thread nor
//   the GPU waits for the compiler. It stops building after `budget` ms (complete: false: run it again later).
//   ready: a promise for the pipelines.
// - lazily(draw) is a real frame that draws what is ready and prepares the rest the same way (building for
//   at most BUILD_MS per frame), to be drawn once its pipeline is: late arrivals (the shores, the carpet, the
//   first trees and cars) show a frame or so later instead of stalling the view. The view's passes are drawn
//   so, and glass's city probe (captured again once complete); the sky map and the impostor bake draw
//   everything at once as before.
// (This stands in for a method of three's Renderer, as its compileAsync does internally; the import map pins
// three's version.)
const BUILD_MS = 30;
// (city.json loading.holdBuildMs, ?holdbuild=: while a change of light is held under the cover (see HOLD_MAX_MS) the
// frames are not seen, so they may build more of the new light's shaders each: Berlin M9 fix round, a Night clicked
// during the warm-up waited 5-10 s under the cover at 30 ms a frame. Off (BUILD_MS) by default)
const HOLD_BUILD_MS = Number(params.get('holdbuild')) || city.loading?.holdBuildMs || BUILD_MS;
const buildMs = () => (held !== null ? HOLD_BUILD_MS : BUILD_MS);
// (?buildlog=1: every node material built, when, for what and how long: __viewer.buildLog)
const buildLog = params.get('buildlog') === '1' ? [] : null;
const leftOut = new Set();                 // (with it: what each frame left out, in the frame log)
const drawObject = renderer._renderObjectDirect;
const prep = { mode: null, budget: 0, deadline: 0, deferred: false, skipped: false, shadows: false, promises: [], maxNew: Infinity,
  maxLinks: Infinity, links0: 0, maxQueue: 1, linkBudget: Infinity, linkMs0: 0, t0: 0, fromStart: false, splitMs: Infinity };
// WebGL 2, once the view is up: at most LINKS_GL new programs per preparation round (a warm-up round, a held change
// of light's round) and per frame drawn, and none while GL_QUEUE are still compiling in the driver (where it compiles
// in the background, KHR_parallel_shader_compile). Without that extension (Chrome's ANGLE on Vulkan here) three
// compiles and links each program at once, and a frame after a change of light asked for every program it met:
// tasks of 0.6-3 s, GPU frames of 3-4 s, and twice the GPU process lost (Berlin M9 fix round). WebGPU builds its
// pipelines asynchronously: no limit there. (?glLinks=<n>)
const IS_GL = renderer.backend.isWebGLBackend;
const LINKS_GL = IS_GL ? Number(params.get('glLinks') || 1) : Infinity;
const GL_QUEUE = 1;
// (a held change of light, with KHR_parallel_shader_compile: up to HELD_LINKS_PAR programs a round and in the driver.
// One at a time, Day after the time slider at the overview waited 7 s for 106 programs of 10-50 ms each, Chrome's
// ANGLE on OpenGL; all at once it had been a 3.7 s task)
const GL_PARALLEL = IS_GL && !!renderer.backend.parallel;
const HELD_LINKS = GL_PARALLEL ? Number(params.get('heldLinks') || 4) : LINKS_GL;
// (with KHR_parallel_shader_compile, a held round on WebGL 2 waited until every program of the round before had linked:
// one slow link (the facades' or glass's, 0.5-1.1 s in the driver) left the driver idle behind it while the next
// materials waited to be built. Singapore M9 fix round, Night clicked during the warm-up: 29 programs, 7.3 s under the
// cover. So the next round is run as soon as fewer than HELD_LINKS are still compiling (the driver's queue kept full);
// the same programs, the same frame at the end: only when they are asked for changes. ?heldfill=0: as before)
const HELD_FILL = GL_PARALLEL && params.get('heldfill') !== '0';
const glQueued = () => glWaiting?.length ?? 0;
renderer._renderObjectDirect = function (object, material, scene, camera, lightsNode, group, clippingContext, passId) {
  if (prep.mode === null) return drawObject.apply(this, arguments);
  const ro = this._objects.get(object, material, scene, camera, lightsNode, this._currentRenderContext, clippingContext, passId);
  if (this._pipelines.get(ro).pipeline === undefined) {
    // (at most maxNew pipelines asked for in one go: see warmStep; at most maxLinks programs: see LINKS_GL)
    if (prep.promises.length >= prep.maxNew) { prep.deferred = true; return; }
    if (prep.maxLinks < Infinity && (linksMade - prep.links0 >= prep.maxLinks || glQueued() >= prep.maxQueue || linkMs - prep.linkMs0 >= prep.linkBudget)) {
      prep.deferred = true;
      return;
    }
    // not prepared yet: its node material built now, unless the time for that is used up (then next time)
    const built = this._nodes.get(ro).nodeBuilderState !== undefined || this._nodes.nodeBuilderCache.has(ro.initialCacheKey);
    if (!built) {
      const now = performance.now();
      prep.deadline ||= (prep.fromStart ? prep.t0 : now) + prep.budget;   // (counted from the first build, or the round's start)
      if (now > prep.deadline) { prep.deferred = true; return; }
    }
    ro.drawRange = object.geometry.drawRange;
    ro.group = group;
    const tb = buildLog && !built ? performance.now() : 0;
    this._nodes.getForRender(ro);
    if (tb) buildLog.push([Math.round(performance.now()), material.name || material.type, object.name || object.type, Math.round(performance.now() - tb),
      this._currentRenderContext?.renderTarget?.texture?.name ?? (this._currentRenderContext?.renderTarget ? 'rt' : 'canvas')]);
    // (a long build's link left to the next round: see WARM_SPLIT_MS)
    if (!built && performance.now() - prep.t0 > prep.splitMs) { prep.deferred = true; prep.linkBudget = -1; return; }
    // (nested passes, such as a pipeline's scene pass, run the same way; shadow maps only if asked for)
    const pre = this._isPreCompiling;
    this._isPreCompiling = !prep.shadows;
    this._nodes.updateBefore(ro);
    this._geometries.updateForRender(ro);
    this._nodes.updateForRender(ro);
    this._bindings.updateForRender(ro);
    this._isPreCompiling = pre;
    this._pipelines.getForRender(ro, prep.promises);
    this._isPreCompiling = true;
    this._nodes.updateAfter(ro);
    this._isPreCompiling = pre;
  } else if (prep.mode === 'dry') {
    // prepared already: only the passes nested in it run on (a pipeline's scene pass)
    const pre = this._isPreCompiling;
    this._isPreCompiling = !prep.shadows;
    this._nodes.updateBefore(ro);
    this._isPreCompiling = pre;
  }
  if (prep.mode === 'lazy' && this._pipelines.isReady(ro)) drawObject.apply(this, arguments);
  // (left out too: its pipeline, asked for in an earlier frame, still compiling. Such a frame counted as complete,
  // and after a change of light the cover went at the first frame drawn before those pipelines were ready: Paris
  // M9 round 4, at the Cité after a night start, a "complete" Day frame followed by 9 with gaps, 80-250 draws)
  else if (prep.mode === 'lazy') {
    prep.skipped = true;
    if (buildLog) leftOut.add(`${material.name || material.type}@${this._currentRenderContext?.renderTarget?.texture?.name ?? 'canvas'}`);
  }
};
// A render object thrown away before its nodes were built (lazily left it for a later frame, then its cache key
// changed: another light, haze, context) costs nothing to drop. three r186's dispose asks it for its bindings to
// free them (Bindings.deleteForRender -> getBindings -> getNodeBuilderState), which builds its whole node material
// first, only to destroy what that made: 37 ms for an average material, ~80 ms for the facades, synchronously inside
// RenderObjects.get, before any build budget can defer it (Paris M9 round 3: 408 of them, 13 s of a 15 s task). Such
// an object has no bindings: it is given none to free
const objectsCreate = renderer._objects.createRenderObject;
renderer._objects.createRenderObject = function (...args) {
  const ro = objectsCreate.apply(this, args);
  const dispose = ro.dispose;
  ro.dispose = function () {
    if (!this._bindings && renderer._nodes.get(this).nodeBuilderState === undefined) this._bindings = [];
    return dispose.call(this);
  };
  return ro;
};
const backendCalls = ['beginRender', 'finishRender', 'clear'];
function preparing(mode, budget, shadows, draw, deadline = 0, maxNew = Infinity, maxLinks = Infinity, maxQueue = GL_QUEUE,
  { linkBudget = Infinity, fromStart = false, splitMs = Infinity } = {}) {
  Object.assign(prep, { mode, budget, deadline, deferred: false, skipped: false, shadows, promises: [], maxNew, maxLinks, links0: linksMade, maxQueue,
    linkBudget, linkMs0: linkMs, t0: performance.now(), fromStart, splitMs });
  const be = renderer.backend;
  if (mode === 'dry') for (const k of backendCalls) be[k] = () => {};
  try {
    draw();
  } finally {
    prep.mode = null;
    if (mode === 'dry') for (const k of backendCalls) delete be[k];
  }
  return { complete: !prep.deferred, ready: Promise.all(prep.promises), pending: prep.promises.length > 0, skipped: prep.skipped };
}
const compileOnly = (draw, budget = Infinity, { shadows = false, maxNew = Infinity, maxLinks = Infinity, maxQueue = GL_QUEUE, ...round } = {}) =>
  preparing('dry', budget, shadows, draw, 0, maxNew, maxLinks, maxQueue, round);
// (the links a frame may still ask for: LINKS_GL across all its lazily drawn passes, from the first frame on screen;
// reset with frameBuildDeadline as each frame begins)
let frameLinks0 = 0;
const frameMaxLinks = () => (!firstShown ? Infinity : glBusyAtFrame ? 0 : Math.max(0, LINKS_GL - (linksMade - frameLinks0)));
let glBusyAtFrame = false;               // (WebGL 2: an earlier frame still on the GPU as this one began: no link in it)
// (one BUILD_MS for all the lazily drawn passes of a frame, counted from its first build: the glass's probe, the
// water's mirror and the view each had a budget of their own, and each could overrun it by one material, so a night
// start's first frames ran 360-450 ms tasks (Paris M9 round 3: the town's probe material 116 ms and the backdrop's
// 145 ms in one frame). frameBuildDeadline is reset as each frame begins)
let frameBuildDeadline = 0;
// again(): what to do so that a capture left incomplete is made again (glass's city probe)
function lazily(draw, again = null) {
  const r = preparing('lazy', buildMs(), true, draw, frameBuildDeadline, Infinity, frameMaxLinks());
  if (r.pending || !r.complete) wlog('lazy', prep.promises.length, r.complete);
  frameBuildDeadline = prep.deadline;
  if (!r.complete || r.pending || r.skipped) frameGaps = true;
  // what was left out is drawn once ready (the shadow map again, it may be missing from it too)
  if (!r.complete) { again?.(); invalidate({ redraw: true }); }
  if (r.pending) r.ready.then(() => { again?.(); invalidate({ shadows: true, redraw: true }); });
  // (left out for a pipeline asked for in an earlier frame and still compiling: no promise of this round's to wait for,
  // so the capture is made again at the next frame, until nothing is left out; before, such a capture with gaps was kept)
  else if (again && r.complete && r.skipped) { again(); invalidate({ redraw: true }); }
}
const hideInProbe = () => [trees.group, cars.group, ...(rooftops ? [rooftops.group] : []),
  ...(PROBE.lean ? [...(lamps ? [lamps.group] : []), ...(probeShores ? [probeShores] : []),
    ...tileGroups.filter((g) => g.userData.masses || g.userData.markings)] : [])];
const probeOptions = () => ({ hide: hideInProbe(), sky, fogDensity: HAZE_DENSITY * settings.haze, lighten: PROBE.lean && probeGround.length ? probeGroundIn : null,
  ground: terrain.height(controls.target.x, controls.target.z) });
// the passes of a frame, settled and moving, for compileOnly: glass's city probe, the water's mirror, the
// occlusion pipeline (with its bloom after dark) and the plain render
// (plain = false: without the frames drawn without occlusion, the moving ones by day; probe = false: without
// glass's city probe)
function framePasses(plain = true, probe = true) {
  updateEnv();
  updateGlow();
  if (settings.cityMirror && probe) cityReflection.prepare(scene, controls.target, probeOptions());
  if (settings.mirror) renderWaterReflection(renderer, scene, camera, { hide: [sky, cars.group] });
  renderSettled();
  if (!plain) return;
  if (glowing) { stillGlow.render(); movingGlow.render(); } else renderer.render(scene, camera);
}
// (city.json loading.passesLater: the first view waits only for the passes of its settled frame, without glass's
// city probe; once it is on screen the moving frames' shaders are prepared, and until they are ready a moving
// frame is drawn through the settled pipeline instead, at the moving resolution, rather than with gaps; and the
// probe is captured then, lazily, glass reflecting the sky alone until it is. The driver compiles the pipelines
// one after another in the GPU's process, which delays any frame submitted after them: so the first frame
// waits for none of these)
let plainReady = true, firstShown = false;
let probeReady = true;                     // (loading.passesLater: glass's probe prepared, see below the loop)
// After dark the moving frames go through a pass of their own (movingGlow), which nothing prepares ahead at night
// (the background warm-up gets to it only once the view is complete): drawn lazily, each moving frame built at
// most BUILD_MS of its shaders and left the rest out, and a slow GPU's first seconds of moving after a night start were frames of a
// dozen draws (Paris M9, Avenue de l'Opéra at 21:30: 14 draws and 2.4 M triangles against 139 / 9.9 M by day). So
// from the moment the lights come on until that pass is prepared (prepareMovingGlow: a little at a time while the
// view is idle or moves, drawing nothing), a moving frame is drawn through the settled pipeline (complete, at the
// moving resolution), as passesLater does by day
let glowMovingReady = true, glowPrep = null;
function prepareMovingGlow(inFrame = false) {
  if (glowMovingReady || glowPrep?.done) return;
  glowPrep ??= { rounds: 0, promises: [] };
  updateGlow();
  // (in a frame, within the frame's one build budget: with one of its own a moving frame after a night start ran two
  // overruns, 380-420 ms tasks at Paris's overview)
  const r = preparing('dry', BUILD_MS, false, () => movingGlow.render(), inFrame ? frameBuildDeadline : 0, Infinity, inFrame ? frameMaxLinks() : LINKS_GL);
  if (inFrame) frameBuildDeadline = prep.deadline;
  glowPrep.promises.push(r.ready);
  if (r.complete || ++glowPrep.rounds >= MAX_ROUNDS) {
    const p = glowPrep;
    p.done = true;
    Promise.all(p.promises).then(() => { if (glowPrep === p) { glowMovingReady = true; glowPrep = null; } });
  }
}
// Day and night shaders, held for good, and the night's compiled ahead, in the background once the city is in
// and the view idle, a little at a time (see the loop). three keeps one render object per mesh, material and
// pass, makes it anew when the light or the haze it was built for changes, and drops a built shader as soon as
// no object uses it: so the first dusk would stall for seconds building and compiling the lit copies of the
// materials (night.js) pass by pass, and every change between day and night after it would throw away the
// shaders of the materials without a lit copy (those only see the haze change) to build them again. Instead
// every pass is run (compileOnly) on stand-ins, the rest of the scene hidden: a mesh for each material and kind
// of geometry in view, sharing them (so the same cache keys), kept, and so their shaders with them. The passes
// of a frame by day; then the sky map (into a throwaway target) and glass's city probe, the water's mirror, the
// occlusion pipeline with its bloom, the glow pipelines and the plain render with the lit copies on, in the
// sun's light and shadows (dusk) and by moonlight. Each step is [light, passes], run until complete.
const WARM_MS = 40, MAX_ROUNDS = 60;       // (a step given up after MAX_ROUNDS, should it never complete)
// WebGL 2: a warm-up round asks for at most WARM_NEW new pipelines, and the next round waits until the driver has
// finished those (warmPending). Asked for a step's worth at once, the programs queued up in the GPU process, and the
// next call that had to wait for it (a link status, a uniform's location) stalled the page: tasks of 1.2 s (London
// M9) to 3.8 s (round 2, 1 load of 2) during the City's background warm-up. WebGPU's pipelines build asynchronously
// without such a wait: no limit there. (?warmnew=<n>)
const WARM_NEW = renderer.backend.isWebGLBackend ? Number(params.get('warmnew') || 1) : Infinity;
const WARM_MAX_ROUNDS = renderer.backend.isWebGLBackend ? 600 : MAX_ROUNDS;
// WebGL 2 without KHR_parallel_shader_compile, while the page is idle (no input for WARM_IDLE_INPUT_MS, nothing on
// the GPU, no change of light held: the loop's conditions), the warm-up works in batches. One link a round and a round
// every 100 ms at most, New York's warm-up had run at ~10 programs a second: 22.6 s at the Manhattan overview and
// 43.5 s at Downtown Brooklyn, against 11.5 and 20 s with the viewer of 30 Sep. Now such a round
// - links up to WARM_IDLE_LINKS programs until WARM_LINK_MS of the main thread went into linking (not LINKS_GL);
// - builds for WARM_IDLE_MS counted from the round's start (a round begun with links builds little), and a material
//   whose build ends past WARM_SPLIT_MS of the round is linked in the next one: Berlin's facades take ~175 ms to build
//   and ~60 ms to link, which in one round made tasks of 240-250 ms;
// - comes WARM_GAP_IDLE_MS after the last one began (not 100).
// Interaction, held changes of light and frames keep LINKS_GL (8986ea9's freezes came from those), WebGPU and drivers
// that compile in the background their own pace. (?warmLinks=1: one at a time as before; ?warmLinks=, ?warmLinkMs=,
// ?warmMs=, ?warmSplit=, ?warmGap=)
const WARM_BATCH = IS_GL && !GL_PARALLEL && Number(params.get('warmLinks') ?? 8) > LINKS_GL;
const WARM_IDLE_LINKS = Number(params.get('warmLinks') || 8);
const WARM_LINK_MS = Number(params.get('warmLinkMs') || 20);
const WARM_IDLE_INPUT_MS = 1000;
const WARM_IDLE_MS = Number(params.get('warmMs') || 60);
const WARM_SPLIT_MS = Number(params.get('warmSplit') || 60);
const WARM_GAP_IDLE_MS = Number(params.get('warmGap') || 40);
// A batch of steps covers the kinds in view that no batch has covered yet: the first when the view is up, then
// (checked every WARM_SCAN_MS while idle) whatever came in since, such as the trees, rooftops, cars,
// shores and carpet further out, so that a change of light later has nothing left to build for them either.
const WARM_SCAN_MS = 5000;
// (paused while the view is moved, a change of light is held, and for this long after any input: a drag, a zoom, a
// click, the time slider; the warm-up's rounds and the frames the input asks for would otherwise share the GPU)
const WARM_AFTER_INPUT_MS = 1000;
const warmedKinds = new Set();
// what an object's shaders depend on: its material, shadows, draw order, instancing and geometry layout
const shaderKind = (o) => {
  const g = o.geometry;
  return [night.dayMaterial(o.material).id, o.receiveShadow, o.castShadow, o.renderOrder, !!o.isInstancedMesh, !!o.instanceColor,
    g.index?.array.constructor.name,
    ...Object.entries(g.attributes).map(([k, a]) => `${k}${a.itemSize}${a.array.constructor.name}${a.normalized}${!!a.isInstancedBufferAttribute}`)].join();
};
function warmSteps() {
  const found = new Map();
  scene.traverseVisible((o) => {
    if (!o.isMesh) return;
    const kind = shaderKind(o);
    if (!warmedKinds.has(kind) && !found.has(kind)) found.set(kind, o);
  });
  // (the street lamps are hidden by day: their shader warmed all the same)
  if (lamps?.meshes.length) { const kind = shaderKind(lamps.meshes[0]); if (!warmedKinds.has(kind)) found.set(kind, lamps.meshes[0]); }
  // (and the signs' light on the street, rooftopLook.signSpill: shown only after dark, once it has instances)
  if (rooftops?.spill?.userData.sa) { const kind = shaderKind(rooftops.spill); if (!warmedKinds.has(kind)) found.set(kind, rooftops.spill); }
  if (!found.size) return [];
  for (const kind of found.keys()) warmedKinds.add(kind);
  const models = [...found.values()];
  return [
    ['day', framePasses],
    // (after dark the day's sky map too, made when the light changes)
    ...night.state.on ? [['day', () => pmrem.fromScene(envScene, 0, 0.1, 100).dispose()]] : [],
    ...!NIGHT_WARM ? [] : [['sun', () => pmrem.fromScene(envScene, 0, 0.1, 100).dispose()]],
    // (the night's and dusk's settled frames first, then their moving ones: a change of light in the first minute
    // finds the frame it is held for prepared sooner. Until the warm-up fix every pass of dusk came before any of
    // the night's)
    ...[[
      () => settings.cityMirror && cityReflection.prepare(scene, controls.target, probeOptions()),
      () => settings.mirror && renderWaterReflection(renderer, scene, camera, { hide: [sky, cars.group] }),
      () => settledGlow.render(), () => stillGlow.render(),
    ], [
      () => movingGlow.render(), () => renderer.render(scene, camera),
    ]].flatMap((group) => (NIGHT_WARM ? ['moon', 'sun'] : []).flatMap((light) => group.map((passes) => [light, passes]))),
  ].map((step) => Object.assign(step, { models }));
}
let warming = [], lastWarm = 0, lastWarmScan = 0;
// (a warm-up round at most every WARM_GAP_MS from the start of the last; WARM_GAP_IDLE_MS in batches, see WARM_BATCH)
const WARM_GAP_MS = 100;
let lastWarmWork = 0;                      // (when a warm-up step or the moving glow's preparation last ran: not a rescan that found nothing)
let warmPending = 0;                       // (steps issued whose pipelines the driver is still compiling)
// what is left of the warm-up. It runs by night too, each step in its own light and the view's restored after: after
// a night start nothing else prepared the day, and the first Day waited 1.5-3 s behind the cover (Paris M9 round 4).
// (Paris M9 round 2 had tried that and every step took 5-10 s, three re-creating the view's render objects at ~37 ms
// each inside RenderObjects.get: the scene pass and the still glow pass then shared a render context, fixed since,
// see scenePass.setMRT.) After dark it waits until a frame has left nothing out: the view's own shaders first
const warmLeft = () => warming.length + warmPending;
let lastGaps = false;                      // (whether the last frame drawn left something out)
const standIns = [];
function warmStep() {
  const step = warming[0], [light, passes] = step;
  const group = step.standIns ??= new THREE.Group();   // (made once per step)
  // a stand-in for each model, instanced like it (an instanced mesh's shaders differ from a plain one's)
  if (!group.children.length) for (const o of step.models) {
    const m = o.isInstancedMesh ? new THREE.InstancedMesh(o.geometry, o.material, 1) : new THREE.Mesh(o.geometry, o.material);
    if (o.instanceColor) m.instanceColor = o.instanceColor;
    Object.assign(m, { receiveShadow: o.receiveShadow, castShadow: o.castShadow, renderOrder: o.renderOrder, frustumCulled: false });
    m.userData.noReflect = o.userData.noReflect;
    group.add(m);
  }
  if (!standIns.includes(group)) standIns.push(group);
  const hidden = scene.children.filter((o) => o.visible && !o.isLight);
  for (const o of hidden) o.visible = false;
  scene.add(group);
  // (the step's light, whichever is on: the lit copies, the haze, the sun or the moon, and the glow; then the view's)
  const was = { on: night.state.on, sun: sun.visible, moon: moon.visible }, on = light !== 'day';
  if (on !== was.on) nightOn(on); else night.apply(group, on);
  sun.visible = light !== 'moon';
  moon.visible = light === 'moon';
  warmLight = light;
  // (by night the day step draws the stand-ins into the sun's shadow map too: after a night start nothing else had
  // prepared its shaders. The first Day at the Cité: 2.5-3.0 s behind the cover without, 1.8 s with; the casters'
  // own shadow materials are still built then, tsl-and-three-pitfalls 42)
  const shadows = light === 'day' && was.on;
  if (shadows) sun.shadow.needsUpdate = true;
  const idle = performance.now() - lastInput > WARM_IDLE_INPUT_MS && !glBusy() && hold === null;
  const batch = WARM_BATCH && idle;
  const r = compileOnly(passes, batch ? WARM_IDLE_MS : WARM_MS, { shadows, maxNew: WARM_NEW, maxLinks: batch ? WARM_IDLE_LINKS : LINKS_GL,
    ...batch ? { linkBudget: WARM_LINK_MS, fromStart: true, splitMs: WARM_SPLIT_MS } : {} });
  wlog('step', warming.length, light, (step.rounds ?? 0) + 1, prep.promises.length, r.complete, linksMade - prep.links0);
  if (shadows) sun.shadow.needsUpdate = true;     // (the next frame by day draws the view's own)
  warmLight = null;
  updateGlow();
  sun.visible = was.sun;
  moon.visible = was.moon;
  if (on !== was.on) nightOn(was.on);
  scene.remove(group);
  for (const o of hidden) o.visible = true;
  step.rounds = (step.rounds ?? 0) + 1;
  if (r.complete || step.rounds >= WARM_MAX_ROUNDS) warming.shift();
  if (r.pending) {
    warmPending++;
    r.ready.finally(() => { warmPending--; });
    r.ready.then(() => { if (lastGaps) invalidate({ redraw: true }); });   // (a change of light came first: draw what was left out)
  }
}

// Day to dusk or back before the background warm-up (warmSteps) got that far (on a phone that may take minutes):
// the lit copies' shaders (or, for materials without one, those for the other haze) aren't built yet, and the
// frames drawn lazily would bring the new light in piece by piece, flickering between the two. So from a change
// of light until the first settled frame that leaves nothing out, a frame that left something out is never
// shown bare: the last complete one, copied onto a canvas over the renderer's, covers it, with a note if it
// takes a moment (while the view is moved too: it waits rather than flickers), for at most HOLD_MAX_MS. The
// view as it was is copied when the light changes, and every complete frame meanwhile. (Only then: things
// arriving later, such as cars and rooftops further out, show a frame late as by day; covering those made the
// moving water and cars jump back and forth. Compiling the passes ahead instead, as at startup, doesn't work
// after dark: it keeps building the same shaders again.)
const HOLD_MAX_MS = 30000, NOTE_MS = 400;
const freezeEl = document.getElementById('freeze'), noteEl = document.getElementById('note');
let hold = null, heldValid = false;      // since when a change of light is held; whether the copy is of this view
let held = null;                         // since when the copy covers the view
let keptMs = 0;                          // (the last copy's main-thread time, for measuring)
function keepFrame() {
  const t = performance.now(), c = renderer.domElement;
  // (the cover sized by settled frames; a moving frame's smaller one is stretched over it)
  if (!moving && (freezeEl.width !== c.width || freezeEl.height !== c.height)) Object.assign(freezeEl, { width: c.width, height: c.height });
  freezeEl.getContext('2d').drawImage(c, 0, 0, freezeEl.width, freezeEl.height);
  heldValid = true;
  keptMs = performance.now() - t;
}
function freezeView() {
  // the view as last drawn (the canvas has been handed to the page since: drawn again, in the light still on)
  // (WebGL 2 with the GPU still on a frame: no copy drawn, the canvas keeps the view as it was, and the held rounds
  // draw nothing until the new light is complete. Drawing it waited for that frame in the click's task, 1.1 s at the
  // Cité. Uncovered, a drag meanwhile shows the frames as they come)
  if (!heldValid && glBusy()) { hold = performance.now(); return; }
  if (!heldValid) {                     // (no copy of this view yet: draw it in the light still on)
    updateGlow();
    if (settledAO) renderSettled(); else renderPlain();
    keepFrame();
    // (WebGL 2: counted as a frame on the GPU, so glBusy knows: the first held round linked a program right after it
    // and waited 0.5 s for it, Mitte)
    if (IS_GL) { if (!inFlight++) lastGpuDone = performance.now(); gpuDone().then(() => { inFlight--; lastGpuDone = performance.now(); }); }
  }
  hold = held = performance.now();
  freezeEl.hidden = false;
}
function uncover() {
  held = null;
  freezeEl.hidden = noteEl.hidden = true;
}
// after each frame drawn while a change of light is held: covered if it left something out, else shown and kept
function presented(now) {
  if (hold === null) return;
  if (now - hold > HOLD_MAX_MS) {            // given up: the view as it comes
    hold = null;
    uncover();
    return;
  }
  if (!frameGaps) {
    uncover();
    keepFrame();
    if (!moving) hold = null;                // (settled and complete: the new light is all there)
    return;
  }
  if (!heldValid) return;
  held ??= now;
  freezeEl.hidden = false;
  if (now - held > NOTE_MS) {
    noteEl.textContent = night.state.on ? 'Preparing the night lights…' : 'Preparing the daylight…';
    noteEl.hidden = false;
  }
}
addEventListener('resize', () => { heldValid = false; });
// While a change of light is held and the view is still, the frames under the cover are not seen: each drew the
// whole view on the GPU (a settled frame 0.3-0.55 s on the test GPU, WebGL 2) to show it left something out, and
// built BUILD_MS of the new light's shaders. Instead the view's passes are prepared without drawing (compileOnly,
// as at startup), a round per animation frame, and the frame is drawn once a round finds nothing left and the
// pipelines asked for are ready. (?heldprep=0: the frames drawn as before)
const HELD_PREP = params.get('heldprep') !== '0';
let heldFresh = false;                    // (the light has just changed: prepare before the first frame)
let heldWait = [], heldRounds = 0, heldDone = false;
// (each held round builds this long: nothing is on screen meanwhile, so more than a frame's BUILD_MS; city.json
// loading.holdBuildMs when set)
const HELD_ROUND_MS = Math.max(HOLD_BUILD_MS, 60);
const HELD_NEXT = params.get('heldnext') !== '0';
function heldPasses() {
  updateEnv();
  updateGlow();
  if (settings.cityMirror) cityReflection.prepare(scene, controls.target, probeOptions());
  if (settings.mirror) renderWaterReflection(renderer, scene, camera, { hide: [sky, cars.group] });
  const ao = settings.ao && camera.position.distanceTo(controls.target) <= 6000;
  (ao ? renderSettled : renderPlain)();
}
// true: a round was run (or its pipelines are still compiling), no frame this time
function heldRound(now) {
  if (!HELD_PREP || heldRounds >= 600 || now - hold > HOLD_MAX_MS - 1000) return false;
  heldFresh = false;
  // (WebGL 2: the next round once the last one's programs are done and the GPU is free; WebGPU builds on while its
  // pipelines compile, and once a round finds nothing left only waits for them)
  if (glBusy(now) || (IS_GL && heldWait.length && !(HELD_FILL && !heldDone && glQueued() < HELD_LINKS)) || (heldDone && heldWait.length)) return true;
  if (heldDone) { heldDone = false; return false; }
  heldRounds++;
  cullTiles();
  // (the sun's shadow map too, when the frame will draw it: by day after a night)
  const due = sun.shadow.needsUpdate;
  if (shadowDirty && !night.state.moon) sun.shadow.needsUpdate = true;
  const r = compileOnly(heldPasses, HELD_ROUND_MS, { shadows: true, maxLinks: HELD_LINKS, maxQueue: HELD_LINKS });
  sun.shadow.needsUpdate = due;
  wlog('held', heldRounds, prep.promises.length, r.complete);
  if (r.pending) {
    const w = r.ready.finally(() => { heldWait = heldWait.filter((x) => x !== w); invalidate({ redraw: true }); });
    heldWait.push(w);
  }
  // (nothing left: the frame now; or, HELD_NEXT, at the next animation frame. The round ran the sun's shadow node
  // (shadows: true) in this animation frame, and three draws a shadow map at most once per frame (ShadowNode's
  // _cameraFrameId): a frame drawn in the same one kept the map as it was, so the first frame after a change of light
  // had no fresh shadows, complete and uncovered, the towers' shadows popping in with the next (Singapore M9 critic,
  // WebGL 2 Night -> Day; WebGPU's first frame there usually left something out and stayed covered). ?heldnext=0: as before)
  if (r.complete && !r.pending && !heldWait.length) {
    if (!HELD_NEXT) return false;
    heldDone = true;
    invalidate({ redraw: true });
    return true;
  }
  if (r.complete) heldDone = true;
  invalidate({ redraw: true });
  return true;
}

const statsEl = document.getElementById('stats');
const backend = renderer.backend.isWebGPUBackend ? 'WebGPU' : 'WebGL 2';
let frames = 0, last = performance.now(), drawnTotal = 0;   // (drawnTotal: every frame drawn, for measuring)
// The stats line says "idle" once no frame has been drawn for a second, whichever way the loop went: it kept the last
// frame's rate ("1 fps · WebGPU · 2x") for as long as the background warm-up, a throttled animation or a change of
// light's preparation returned before drawing, and Berlin's saved shots (taken during the warm-up) read as views
// redrawing once a second for ever where nothing was drawn (Berlin M9: 0 frames, 0 render calls 10 s after the
// animation's stop at the Spree and Kreuzberg). The last frame's triangles and draws stay on its second line
// (at idle the second line is the last settled frame's: it showed whichever frame came last, an animating one's counts
// (the overlay's few draws) or a moving one's, and read against the speed test's settled counts it looked wrong
// (Singapore M9 critic). settledInfo: the last settled frame's)
let lastFrameAt = 0, statsInfo = '', statsIdleText = null, settledInfo = '';
// (after each frame drawn: its triangles and draws, and every 500 ms, or at once after idle, the rate)
const statsFrame = (now, what) => {
  frames++; drawnTotal++;
  lastFrameAt = now;
  statsInfo = `${(renderer.info.render.triangles / 1e6).toFixed(2)} M triangles · ${renderer.info.render.drawCalls} draws`;
  if (what === '' && !moving) settledInfo = statsInfo;
  if (now - last <= 500 && statsIdleText === null) return;
  statsEl.innerHTML = `${what}${((1000 * frames) / (now - last)).toFixed(0)} fps · ${backend} · ${renderer.getPixelRatio()}x<br>${statsInfo}`;
  statsIdleText = null;
  frames = 0;
  last = now;
};
// (every tick: "idle" once nothing has been drawn for 1.5 s, "preparing shaders" while the warm-up works)
let animWhy = '';                // (city.json animation.reason: why nothing animates, set by the loop)
const statsIdle = (now) => {
  if (now - lastFrameAt < 1500) return;
  const text = `idle · ${backend}${warming.length || warmPending ? ' · preparing shaders' : ''}${animWhy ? ` · ${animWhy}` : ''}`;
  if (text === statsIdleText) return;
  const info = settledInfo || statsInfo;
  statsEl.innerHTML = `${text}${info ? `<br>${info}` : ''}`;
  statsIdleText = text;
  frames = 0;
  last = now;
};
// when the GPU has finished what was submitted so far: WebGPU tells; WebGL 2 is asked with a fence, polled
function gpuDone() {
  const device = renderer.backend.device;
  if (device) return device.queue.onSubmittedWorkDone();
  const gl = renderer.backend.gl;
  const sync = gl?.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
  if (!sync) return Promise.resolve();
  gl.flush();
  return new Promise((resolve) => {
    const poll = () => {
      if (gl.isContextLost() || gl.getSyncParameter(sync, gl.SYNC_STATUS) === gl.SIGNALED) { gl.deleteSync(sync); resolve(); }
      else setTimeout(poll, 2);
    };
    poll();
  });
}
// the last FRAME_LOG frames drawn, for measuring (__viewer.frames()): when, which kind (moving, settled,
// animating), at what resolution, whether something was left out or the cover was up, day or night, and the
// ms from the start of the frame until the GPU had finished it
const FRAME_LOG = 300, frameLog = [];
// frames submitted and not yet finished by the GPU (the loop draws no more while MAX_IN_FLIGHT are), and when
// the GPU last finished one; the GPU time of the last moving frame (the shadow map's pace while moving)
const MAX_IN_FLIGHT = 2;
let inFlight = 0, lastGpuDone = 0, movingMs = 0;
// (WebGL 2: a frame still on the GPU, unless it hasn't answered for 2 s)
// (6 s: Paris's frames during the warm-up took the GPU up to 3.4 s on WebGL 2, and with 2 s the first held round's link
// waited 1.3 s for one of them)
const glBusy = (now = performance.now()) => IS_GL && inFlight > 0 && now - lastGpuDone < 6000;
function logFrame(now, kind) {
  const f = { t: now, kind, pr: renderer.getPixelRatio(), gaps: frameGaps, covered: !freezeEl.hidden, night: night.state.on, ms: null, kept: keptMs,
    draws: renderer.info.render.drawCalls, triangles: renderer.info.render.triangles };
  keptMs = 0;
  if (buildLog) { f.left = [...leftOut]; leftOut.clear(); }
  frameLog.push(f);
  if (frameLog.length > FRAME_LOG) frameLog.shift();
  if (!inFlight++) lastGpuDone = now;
  return gpuDone().then(() => {
    lastGpuDone = performance.now();
    inFlight--;
    f.ms = lastGpuDone - now;
    if (kind === 'moving') movingMs = f.ms;
    if (kind === 'settled' && !f.covered) settledMs = f.ms;
    return f;
  });
}

// shadows: a frustum sized to the view around the orbit target. Re-rendered at most every
// SHADOW_MS while the view moves (so they follow smoothly at a fraction of the per-frame cost),
// immediately when the target has moved a quarter of it or the zoom changed by a third, and once
// more when the view settles
const SHADOW_MS = 100;
const shadowAt = new THREE.Vector3(Infinity, 0, 0);
let shadowSpan = 0, shadowTime = 0;
function updateSun(force) {
  const span = THREE.MathUtils.clamp(camera.position.distanceTo(controls.target) * 1.2, 800, 6000);
  const moved = shadowAt.distanceTo(controls.target) > shadowSpan * 0.25;
  const rescaled = Math.abs(span - shadowSpan) > shadowSpan / 3;
  // (while the view turns round a fixed target nothing moves in the map but refilled instances: every two or
  // three frames' worth is enough; a 100 ms limit redrew the 2048 px map on every frame of a slow GPU, while a
  // fixed 400 ms one would freeze the shadows for a dozen frames on a fast one)
  const stale = performance.now() - shadowTime > (moving ? Math.max(SHADOW_MS, 2.5 * movingMs) : SHADOW_MS);
  if (!(force || moved || rescaled || stale)) return;
  shadowTime = performance.now();
  const cam = sun.shadow.camera;
  cam.left = cam.bottom = -span;
  cam.right = cam.top = span;
  cam.updateProjectionMatrix();
  sun.target.position.copy(controls.target);
  sun.position.copy(controls.target).addScaledVector(lightDir, 6000);
  moon.position.copy(sun.position);
  sun.shadow.needsUpdate = !night.state.moon;         // no shadow pass by moonlight
  if (shadowTrim && !night.state.moon) shadowTrim.updateSun(THREE.MathUtils.radToDeg(Math.asin(THREE.MathUtils.clamp(lightDir.y, -1, 1))));
  shadowAt.copy(controls.target);
  shadowSpan = span;
}

// The glass's city probe and the water's mirror are drawn before the view, with the trees, rooftops and cars
// hidden: a shadow map due this frame is left to the view (drawn in the first of them, it would lack those, and
// their shadows went missing after a change of light until the view moved)
function afterShadows(draw) {
  const due = sun.shadow.needsUpdate;
  sun.shadow.needsUpdate = false;
  try { draw(); } finally { sun.shadow.needsUpdate = due; }
}

// skip tiles the fog hides anyway: beyond a radius that grows with the view distance
// (city.json masses.housesNear: London's terraces are most of its outer boroughs, drawn from the overview too)
const MASS_HOUSES = city.masses?.housesNear ?? 6000;
// (city.json markings.far, m, opt-in: a markings tile or block is drawn only while the camera is within this distance
// of its nearest point, the camera's height included: from high up the lines are under a pixel and cost a whole
// pass of thin triangles (Hong Kong M6: ~30 ms at the overview); unset: the fog radius as before)
const MARK_FAR = city.markings?.far ?? 0;
function cullTiles() {
  const radius = Math.min(60000, 9000 + 3 * camera.position.distanceTo(controls.target));
  for (const g of tileGroups) {
    const t = g.userData.tile;
    const dx = t.x + t.size / 2 - camera.position.x, dz = t.z + t.size / 2 - camera.position.z;
    g.visible = dx * dx + dz * dz < radius * radius && (settings.markings || !g.userData.markings) && (settings.masses || !g.userData.masses);
    if (MARK_FAR && g.visible && g.userData.markings) {
      const nx = Math.max(t.x - camera.position.x, 0, camera.position.x - t.x - t.size);
      const nz = Math.max(t.z - camera.position.z, 0, camera.position.z - t.z - t.size);
      g.visible = Math.hypot(nx, nz, Math.max(camera.position.y, 0)) < MARK_FAR;
    }
    // the town masses' houses (06e_masses): only within MASS_HOUSES m of the camera, over the cell's nearest point
    if (g.userData.small) {
      const nx = Math.max(t.x - camera.position.x, 0, camera.position.x - t.x - t.size);
      const nz = Math.max(t.z - camera.position.z, 0, camera.position.z - t.z - t.size);
      g.userData.small.visible = Math.hypot(nx, nz, camera.position.y) < MASS_HOUSES;
    }
  }
}

controls.addEventListener('change', () => invalidate());
let moving = false, lastChange = 0;

// ---------------------------------------------------------------- moving water and traffic
// With the Waves switch on (?waves=0 or the menu: off), the water moves (water.js); with the Traffic switch
// on, so do the cars (cars.js). While enough water or moving cars are in view (cars.active(): lanes within
// 1.5 km of the camera) and the tab is visible, the settled view is redrawn WAVE_FPS times a second, and those frames
// only redraw: no shadow map, no mirrored city (the camera has not moved), no tree or tile updates, and
// the ambient occlusion of the last settled frame is reused instead of recomputed (its pre-pass and SSAO
// are frozen). Water and traffic share a clock that only runs while it is drawn, so nothing jumps after a pause.
settings.waves = feature('waves', 'waves');
const WAVE_FPS = 24;
// nobody watching closely: after WAVE_SLOW_S seconds without input the waves drop to half rate, and
// after WAVE_STOP_S they stop until the next touch (the view stays on its last frame)
const WAVE_SLOW_S = 30, WAVE_STOP_S = 180;
// The animation is paced by the GPU too: after an animating frame that took d ms to finish, d/2 ms of rest (at most
// two thirds of the GPU's time; a frame every 1.5 d), and after WAVE_SLOW_S d*2 (a frame every 3 d: half the rate).
// Where two animating frames in a row take the GPU over ANIM_SLOW_MS (under ~10 frames a second) it stops at once,
// until the view or the light changes: at 1-5 frames a second moving water reads as a glitch (Paris M5 critic, 351
// ms frames on an Iris Xe), still water doesn't. Decided by what an animating frame costs, measured at each view,
// not by the settled frame: Paris's settled frames (with occlusion's passes) took over the old 150 ms limit in
// every view, so nothing ever moved, while an animating frame at the Opéra street takes 56 ms (Paris M9 round 2:
// 12 frames a second, then 6). (?animslow=<ms>)
// (city.json animation.gate 'frame'; the default, 'settled', is the rule before it: started only where the settled
// frame takes <= ANIM_SETTLED_MS, half the GPU's time, stopped after WAVE_STOP_SLOW_S where frames take > 100 ms)
// (city.json animation.webgpuOnly, off by default; Tokyo M9: the city's gate and full apply on WebGPU only, where the
// overlay makes an animating frame the cars' and the water's own few draws; on WebGL 2, without the overlay, a full frame
// redrew the whole city at ~3.5 fps until the 180 s stop (Singapore M9 critic round 2): there the defaults, 'settled' and
// no full)
const ANIM_CFG = city.animation.webgpuOnly && IS_GL ? { ...city.animation, gate: 'settled', full: false } : city.animation;
const ANIM_BY_FRAME = (params.get('animgate') ?? ANIM_CFG.gate) === 'frame';
const ANIM_SLOW_MS = Number(params.get('animslow')) || city.animation.slowMs, ANIM_SETTLED_MS = 150, WAVE_STOP_SLOW_S = 20;
let animSlowRun = 0;
// city.json animation.full (off by default; ?animfull=0|1): one rule for waves and traffic, at full resolution always
// (never the moving resolution, which blurred the buildings while the traffic moved: Berlin, on a Mac), without the
// costly extras: where the overlay can (WebGPU, by day) the city is drawn once into a picture of the settled frame
// (see ANIM_OVERLAY, on with it) and each animating frame is that picture with the cars and the water over it; else
// a full frame, its occlusion and the water's mirror as the settled frame left them; nothing animates while the
// overlay's shaders are still being prepared (no full frames meanwhile). The same "too slow" rule: stopped where
// two animating frames in a row take > slowMs. (It replaced animation.cheap, removed since: London's and Berlin's
// fallback of animating frames at the moving resolution, without occlusion or multisampling, which blurred the
// city while the traffic moved)
const ANIM_FULL = (params.get('animfull') ?? (ANIM_CFG.full ? '1' : '0')) === '1';
// city.json animation.reason (off by default): the stats line says why nothing animates once idle: "stopped: no
// input", "stopped: too slow (95 ms)", "nothing animating in view"
const ANIM_REASON = !!city.animation.reason;
let animSlowMs = 0;              // (the frame that stopped the animation as too slow: its ms, for the stats line)
let overlayShown = false;        // (animating frames drawn from the overlay's picture: the settled view redrawn after)
let settledMs = 0;
// the overlay (on with animation.full; WebGPU only): animating frames by day draw the city (without its
// cars and water) once into a picture of its own (colour and depth, the canvas's
// format and multisampling, so the same render objects and pipelines: nothing compiled), then each frame only that
// picture (a full-screen quad writing its colour and depth) and the cars and the water over it, at full resolution. What a
// whole frame cost (the city again, 59 ms at the Strand on the Iris Xe: 5 fps near the 70 ms gate) becomes the cars'
// own few draws. The picture is made again after any other frame (the view moved, settled, tiles came, the light
// changed). The quad's depth is the first sample of each pixel's four: a car's edge against a wall in front of it is
// not antialiased. (?animoverlay=0: animation.full without it, full frames; city.json animation.overlay, which put it
// on the cheap frames, went with them)
const ANIM_OVERLAY = ANIM_FULL && params.get('animoverlay') !== '0' && reversedDepth;
// city.json animation.overlayWater (off by default; ?overlaywater=0|1): the water stays in the overlay's picture and is
// drawn again over it each frame (with the shallows' veils that lie on it), rather than left out of it. Left out, the
// picture had nothing under a sea plane but the cleared background, and a pixel on the sea's edge, its colour
// the resolved mix of its four samples (the quay and that background) and its depth the first sample's (the quay's),
// kept the water from being drawn over it: a 1-px bright line along every quay, seawall and pontoon while the waves
// moved (Hong Kong, 6 Oct; the river cities' water lies on the ground, darker under it). The water's surface doesn't
// move (its waves are in the shading), so the frame's water meets the picture's at the same depth and covers it
const ANIM_OVERLAY_WATER = ANIM_OVERLAY && (params.get('overlaywater') ?? (city.animation.overlayWater ? '1' : '0')) === '1';
// city.json animation.overlayLattice (off by default; ?overlaylattice=0|1): the open lattices (lattice.js: the Eiffel
// Tower's braced panels, glazing, fabric) left out of the overlay's picture too and drawn over it each frame, after
// the water. They blend and write no depth, so in the picture whatever lay behind them kept its depth: where that was
// the river (left out of the picture and drawn again each frame, or kept in it with overlayWater: the same depth, and
// the frame's water covers what is in the picture there), the frame's water was drawn over the lattice, and
// wherever the tower stood against the Seine its panels vanished while the traffic moved, leaving the solid chords
// (Paris, 7 Oct; the user's shot). Drawn after the picture and the water, they blend over them as in the settled frame
const ANIM_OVERLAY_LATTICE = ANIM_OVERLAY && (params.get('overlaylattice') ?? (city.animation.overlayLattice ? '1' : '0')) === '1';
const overlay = (() => {
  if (!ANIM_OVERLAY) return null;
  const LAYER = 7;                                 // (drawn with the camera on this layer only: the quad, the cars, the lights)
  const target = new THREE.RenderTarget(1, 1, { type: renderer.getOutputBufferType(), samples: renderer.samples,
    depthBuffer: true, stencilBuffer: renderer.stencil });
  target.depthTexture = new THREE.DepthTexture(1, 1);
  target.depthTexture.type = THREE.FloatType;
  // a full-screen quad writing a picture's colour and depth, texel by texel (the picture must have the canvas's size,
  // see o.fits). The colour passed through as it is (outputNode: no lighting, no fog), linear like the frame's own
  const quadFor = (colourTex, depthTex, name) => {
    const m = new THREE.MeshBasicNodeMaterial();
    m.vertexNode = vec4(positionGeometry.xy, 0, 1);
    m.outputNode = vec4(texture(colourTex).load(ivec2(screenCoordinate.xy)).rgb, 1);
    m.depthNode = texture(depthTex).load(ivec2(screenCoordinate.xy)).x;
    m.depthTest = false;
    m.fog = false;
    m.name = name;
    const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), m);
    quad.frustumCulled = false;
    quad.renderOrder = -1e9;
    quad.layers.set(LAYER);
    quad.visible = false;                          // (only while drawn: the warm-up's scan for kinds of mesh skips it)
    scene.add(quad);
    return quad;
  };
  // Two kinds of picture, after the settled frame they stand in for (London M9 round 2: made by a plain render
  // under a frame that has occlusion, the picture was ~9 % brighter than the settled frame, the Thames lighter, no
  // occlusion at the buildings' feet, and the view jumped at each start and stop of the traffic):
  // - 'plain' (the settled frame draws no occlusion: far views, Occlusion off): the city drawn plainly into `target`;
  // - 'ao': the settled frame's own scene pass (scenePass: the occlusion in the materials' ambient light), drawn again
  //   without the cars and the water, the occlusion texture as the settled frame left it (same view); each overlay
  //   frame then draws its colour and depth, the cars and the water through a pass of the same kind (overPass: the
  //   same occlusion context, 4 samples) and the settled pipeline's last step, the occlusion multiplied in, tone
  //   mapping and output, over the whole: so the picture, the water and the cars come out as in the settled frame
  const plainQuad = quadFor(target.texture, target.depthTexture, 'overlay');
  const aoQuad = quadFor(scenePass.renderTarget.texture, scenePass.renderTarget.depthTexture, 'overlay-ao');
  const overPass = pass(scene, camera, { samples: 4 });
  overPass.setMRT(mrt({ output }));
  overPass.contextNode = scenePass.contextNode;
  overPass.setLayers(new THREE.Layers());
  overPass.getLayers().set(LAYER);
  const overPipe = new THREE.RenderPipeline(renderer);
  overPipe.outputNode = vec4(overPass.rgb.mul(mix(float(1), aoTex, float(0.45))), overPass.a);
  const size = new THREE.Vector2();
  const o = { valid: false, ready: false, preparing: false, mode: 'plain' };
  // (made at another resolution, the picture is made again: the first one, made while the frames were still the moving
  // resolution's, had its depth read at the wrong pixels, and cars showed through walls)
  o.fits = () => { renderer.getDrawingBufferSize(size);
    const t = o.mode === 'ao' ? scenePass.renderTarget : target; return t.width === size.x && t.height === size.y; };
  // the city without the cars and the water into the picture (the frame's own camera, shadow map and mirror as they are)
  o.capture = (mode = settledAO ? 'ao' : 'plain') => {
    o.mode = mode;
    renderer.getDrawingBufferSize(size);
    if (mode === 'plain' && (target.width !== size.x || target.height !== size.y)) target.setSize(size.x, size.y);
    // (the water left out of the picture too, and drawn over it each frame: it moves)
    const water = [];
    scene.traverseVisible((x) => { if (x.isMesh && (x.material?.userData?.water || (ANIM_OVERLAY_WATER && x.userData.overWater))) water.push(x); });
    for (const w of water) { if (!ANIM_OVERLAY_WATER) w.visible = false; w.layers.enable(LAYER); }
    // (the lattices: out of the picture, on the overlay's layer: drawn over the picture and the water each frame)
    if (ANIM_OVERLAY_LATTICE) {
      const lat = [];
      scene.traverseVisible((x) => { if (x.isMesh && x.material?.userData?.lattice) lat.push(x); });
      for (const l of lat) { l.visible = false; l.layers.enable(LAYER); water.push(l); }
    }
    const before = renderer.getRenderTarget();
    // (drawn like a lazy frame: what isn't built yet for this pass is built within the frame's budget and the rest
    // left for later, and a picture that left something out isn't used. Drawn at once, the scene pass built every
    // render object it hadn't drawn yet, trees and rooftops streamed in since the last settled frame: a 1.7 s task
    // at the Strand during the warm-up)
    let r;
    try {
      r = preparing('lazy', BUILD_MS, true, () => {
        if (mode === 'ao') cars.without(() => scenePass.updateBefore({ renderer }));
        else { renderer.setRenderTarget(target); cars.without(() => renderer.render(scene, camera)); }
      }, frameBuildDeadline);
      frameBuildDeadline = prep.deadline;
    } finally { for (const w of water) w.visible = true; renderer.setRenderTarget(before); }
    o.valid = r.complete && !r.pending && !r.skipped;
    // (the lights and the cars on the overlay's layer too: the same light set, so the cars' render objects stay as they are)
    scene.traverse((x) => { if (x.isLight) x.layers.enable(LAYER); });
    for (const c of cars.meshes) c.layers.enable(LAYER);
  };
  // the picture and the cars and the water over it, to the canvas
  const drawWith = (mode) => {
    const quad = mode === 'ao' ? aoQuad : plainQuad;
    quad.visible = true;
    // (the occlusion as the settled frame left it: its pre-pass and SSAO, which the last step's aoTex would otherwise run
    // again in every overlay frame, a whole scene pass more: 78-93 ms frames at the Strand instead of ~12, and the
    // traffic stopped)
    if (mode === 'ao') { freezeAO(true); try { overPipe.render(); } finally { freezeAO(false); quad.visible = false; } return; }
    const mask = camera.layers.mask;
    camera.layers.set(LAYER);
    try { renderer.render(scene, camera); } finally { camera.layers.mask = mask; quad.visible = false; }
  };
  o.draw = () => drawWith(o.mode);
  // the quads' shaders and the overlay pass's prepared (after a first capture: the lights and cars on its layer), a
  // little per animating frame (WARM_MS of node building, as a warm-up step: the overlay pass's render objects for
  // the cars and the water are its own, and built at once they made a 1.7 s task at the Strand), then usable once
  // their pipelines are; until then nothing animates (see ANIM_FULL)
  let rounds = 0;
  const promises = [];
  o.prepare = () => {
    if (o.preparing) return;
    if (!rounds) o.capture();
    const r = compileOnly(() => { drawWith('plain'); drawWith('ao'); }, WARM_MS, { maxLinks: LINKS_GL });
    promises.push(r.ready);
    if (r.complete || ++rounds >= MAX_ROUNDS) {
      o.preparing = true;
      Promise.all(promises).then(() => { o.ready = true; });
    }
  };
  return o;
})();
// "input" is anything that changes the view or the page: clicks, wheel, keys, view changes, the menu.
// Merely moving the pointer across the page does not count (it kept the waves running at full rate).
let lastInput = performance.now();
const touched = () => { lastInput = performance.now(); };
for (const ev of ['pointerdown', 'wheel', 'keydown', 'input']) addEventListener(ev, touched, { passive: true, capture: true });
controls.addEventListener('change', touched);
let massAoCutOn = true;                      // (masses.aoCut, switchable for measuring)
let waveTime = 0, waveClock = performance.now(), lastWaveFrame = 0, settledAO = false;
let animRestUntil = 0, animCost = 0, animBusy = 0;   // (GPU pacing of the animation: see the loop; animBusy: ms in all)
// cars stay out of the occlusion pre-pass: that AO is reused while traffic moves and would keep dark halos
// where the cars were (they have planar shadows of their own). The pre-pass runs nested in the scene pass
// and shares its render list, so the cars are emptied rather than hidden (cars.js)
const prePassUpdate = prePass.updateBefore;
prePass.updateBefore = function (frame) { return cars.without(() => prePassUpdate.call(this, frame)); };
// (city.json masses.aoCut: the town masses' chunks wholly beyond AO_FAR of view depth, where the occlusion has faded
// out, drawn as nothing in the pre-pass: emptied, not hidden, as the cars are, since it shares the scene pass's list)
if (MASS_AO_CUT) {
  const inner = prePass.updateBefore, cut = [], c = new THREE.Vector3();
  const nearestDepth = (b) => {
    let d = Infinity;
    for (let i = 0; i < 8; i++) {
      c.set(i & 1 ? b.max.x : b.min.x, i & 2 ? b.max.y : b.min.y, i & 4 ? b.max.z : b.min.z).applyMatrix4(camera.matrixWorldInverse);
      d = Math.min(d, -c.z);
    }
    return d;
  };
  prePass.updateBefore = function (frame) {
    if (massAoCutOn) {
      camera.updateMatrixWorld();
      for (const m of massAo) if (m.geometry.drawRange.count !== 0 && nearestDepth(m.userData.massBox) > AO_FAR + 100) { cut.push(m); m.geometry.drawRange.count = 0; }
    }
    try { return inner.call(this, frame); } finally { for (const m of cut) m.geometry.drawRange.count = Infinity; cut.length = 0; }
  };
}
const aoNodes = [prePass, aoPass];
const aoUpdate = aoNodes.map((n) => n.updateBefore);
const freezeAO = (frozen) => aoNodes.forEach((n, i) => { n.updateBefore = frozen ? () => {} : aoUpdate[i]; });
const tickWater = (now, animate) => {
  // the clock runs for whatever animates (the cars keep it too); the water takes it only while the waves
  // are on, so switching them off freezes the water even while traffic still moves
  if (filmClock !== null) {                      // (filming: the script's clock, see film below)
    waveTime = filmClock;
    if (settings.waves) setWaterTime(waveTime);
    waveClock = now;
    return;
  }
  if (animate) {
    waveTime += Math.min(now - waveClock, 100) / 1000;
    if (settings.waves) setWaterTime(waveTime);
  }
  waveClock = now;
};

renderer.setAnimationLoop(() => {
  const now = performance.now();
  if (!shown) {
    // the loading screen is up: nothing drawn yet, but the trees, rooftops and cars around the view stream in
    if (dirty && now - lastChange > 100) {
      dirty = false;
      lastChange = now;
      cullTiles();
      if (!LOADING.deferLayers) {
        trees.update(false);
        rooftops?.update(false);
        cars.update(waveTime, false);
      }
    }
    return;
  }
  statsIdle(now);                              // (whatever the loop does next: see statsIdle)
  if (controls.update()) invalidate();        // damping still easing out
  if (dirty && followGround()) invalidate();  // only when the view moved
  // no new frame while the GPU is still on the last one: drawn faster than a slow GPU finishes them (moving),
  // frames queued 5-7 deep and the picture trailed the pointer by 0.7 s; the next tick draws with the newest
  // camera instead (unless the GPU hasn't answered for 2 s)
  if (dirty && inFlight >= MAX_IN_FLIGHT && now - lastGpuDone < 2000) return;
  // WebGL 2: a change of resolution (from settled to moving and back) or a program linked while the GPU is still on
  // an earlier frame waits for it on the main thread: at Mitte a settled frame takes the test GPU 0.5-2 s and the
  // next moving frame's task was 0.6-0.8 s. So those wait, without blocking, until the GPU is done (see glBusy)
  if (dirty && viewDirty && !moving && glBusy(now)) return;
  // (a change of light held while the time slider is still dragged: nothing until it rests, see TIME_REST)
  // (counted as settled meanwhile: once it rests the held rounds start at once, not after a moving frame and 250 ms.
  // Checked before the moving frames' branch: after it, each tick of the drag set the moving resolution there and the
  // settled one here, two canvas resizes a tick for as long as the slider moved; and on WebGL 2 the resolution changes
  // only once the GPU is done, see glBusy)
  if (dirty && hold !== null && TIME_REST && now - timeDragAt < TIME_REST_MS) {
    viewDirty = false;
    if (moving && !glBusy(now)) { moving = false; renderer.setPixelRatio(settings.resolution); }
    return;
  }
  if (dirty && viewDirty && filmClock !== null) viewDirty = false;   // (filming: every frame is a settled one; a moving
  // frame at the lower resolution between the script's frames flickered the visible window between two sizes)
  if (dirty && viewDirty) {
    // (the time slider dragged: city.json time.sliderResolution, see SLIDER_RES)
    const pr = SLIDER_RES && now - timeDragAt < 250 ? Math.min(settings.movingResolution, SLIDER_RES) : settings.movingResolution;
    if (!moving) { moving = true; renderer.setPixelRatio(pr); } else if (SLIDER_RES && renderer.getPixelRatio() !== pr) renderer.setPixelRatio(pr);
    animSlow = false;                            // (a new view: its first animating frame decides again)
    overlayShown = false;
    lastChange = now;
  } else if (dirty) {
    // only a redraw: in the view's state as it is, moving or settled; merged with any that follow shortly (not
    // while a change of light is held: its cover waits for them)
    if (hold === null && now - lastDrawnAt < REDRAW_MS) return;
    // (WebGL 2: not while the GPU is on an earlier frame. A frame begun then links nothing, glBusyAtFrame, so a
    // redraw for what it left out came at once, found the GPU busy again, linked nothing: frames with gaps for good)
    if (glBusy(now)) return;
    // (a redraw once the view has been still for 250 ms, while a change of light is held or on WebGL 2: drawn settled.
    // The redraws for what moving frames left out kept the view moving, the settling below never came first, and the
    // held change waited for moving frames that may link nothing: Night at Mitte on WebGL 2 16.6 s under the cover)
    if (moving && now - lastChange > 250 && (hold !== null || IS_GL)) {
      moving = false;
      renderer.setPixelRatio(settings.resolution);
      shadowDirty = true;
    }
  } else if (moving && now - lastChange > 250 && !glBusy(now)) {
    // settled: one last frame at full resolution with fresh shadows
    moving = false;
    renderer.setPixelRatio(settings.resolution);
    dirty = true;
    shadowDirty = true;
  } else if (!glowMovingReady && glowing && firstShown && !moving && now - lastWarm > 100) {
    // idle after dark: a little more of the moving frames' pass prepared, no frame drawn
    prepareMovingGlow();
    lastWarm = lastWarmWork = now;
    return;
  } else if ((warming.length || now - lastWarmScan > WARM_SCAN_MS) && !moving && !(night.state.on && lastGaps) && now - lastInput > WARM_AFTER_INPUT_MS
    && hold === null && !glBusy(now)
    && !(WARM_NEW < Infinity && warmPending > 0)
    && now - lastWarm > (WARM_BATCH ? WARM_GAP_IDLE_MS : WARM_GAP_MS) && document.visibilityState === 'visible') {
    // idle (after dark once a frame left nothing out): a little more of the shaders prepared (see warmSteps), no
    // frame drawn with it (its passes
    // count as updated for this frame); or, all done, a look for kinds that came in since
    if (!warming.length) { lastWarmScan = now; warming = warmSteps(); }
    if (warming.length) { warmStep(); lastWarmWork = now; }
    lastWarm = now;
    return;
  }
  const idleS = (now - lastInput) / 1000;
  const waveFps = idleS < WAVE_SLOW_S ? WAVE_FPS : WAVE_FPS / 2;
  const animWater = settings.waves && waterInView(camera) > 0, animCars = settings.traffic && cars.active();
  // (not while the settled frame is still on the GPU: no animating frame queued behind it)
  const animOn = idleS < (!ANIM_BY_FRAME && animCost > 100 ? WAVE_STOP_SLOW_S : WAVE_STOP_S) && document.visibilityState === 'visible' && (animWater || animCars)
    && filmClock === null && (ANIM_BY_FRAME ? !animSlow : settledMs <= ANIM_SETTLED_MS);
  const animate = animOn && !(inFlight > 0 && !moving && !dirty);
  // the overlay's frames shown and the animation over: the settled view once more
  if (overlayShown && !animOn && !dirty && !moving && inFlight === 0) {
    overlayShown = false;
    dirty = true;
  }
  const animWhat = [animWater && 'waves', animCars && 'traffic'].filter(Boolean).join(' + ');
  if (ANIM_REASON) {
    animWhy = !(settings.waves || settings.traffic) ? ''
      : !(animWater || animCars) ? 'nothing animating in view'
      : ANIM_BY_FRAME && animSlow ? `stopped: too slow (${Math.round(animSlowMs)} ms)`
      : !ANIM_BY_FRAME && settledMs > ANIM_SETTLED_MS ? `stopped: too slow (${Math.round(settledMs)} ms)`
      : idleS >= (!ANIM_BY_FRAME && animCost > 100 ? WAVE_STOP_SLOW_S : WAVE_STOP_S) ? 'stopped: no input'
      : document.visibilityState !== 'visible' ? 'stopped: page hidden' : '';
  }
  if (!dirty) {
    if (animate && !moving) {
      // throttled: at least 1000 / waveFps ms since the last animating frame (a fixed beat with 4 ms of slack let
      // frames come 38 ms apart: 25 fps read at the Strand, over the 24 fps cap; London M9 round 2). On a 60 Hz
      // display that is every third vsync, 20 fps
      if (now - lastWaveFrame < 1000 / waveFps) return;
      // and never more than two thirds of the GPU's time, a third after WAVE_SLOW_S (see ANIM_SLOW_MS; on a slow
      // GPU an animating frame costs as much as a full one, and the 24 fps cap alone kept it at 100 %)
      if (now < animRestUntil) return;
      // (animation.full: the overlay's shaders prepared first, a little per tick, nothing animating meanwhile)
      if (ANIM_FULL && overlay && !overlay.ready && !glowing) {
        overlay.prepare();
        lastWaveFrame = waveClock = now;
        statsIdle(now);
        return;
      }
      lastWaveFrame = now;
      tickWater(now, true);
      cars.update(waveTime);
      updateGlow();
      frameGaps = false;
      frameBuildDeadline = 0;
      frameLinks0 = linksMade;
      glBusyAtFrame = glBusy(now);
      // (the cars over a picture of the city, where that is on: see ANIM_OVERLAY)
      const overlaid = overlay?.ready && !glowing;
      updateEnv();
      let captured = false;              // (a frame that made the overlay's picture first: not counted as slow)
      // While the background warm-up works (a step in the last 1.5 s, steps left, or pipelines it asked for still
      // compiling) the GPU process's pipeline builds delay the frames: 72-244 ms at the Strand in London M8, and the
      // traffic stopped for good at the first two. Such slow frames never stop the animation, in every city: until
      // London M9 round 2 only cheap frames (animation.cheap, since removed) were exempt, and Paris's Pont des Arts
      // (full frames) stopped at once in one run of two: its first animating frame took 101.6 ms (54 ms otherwise)
      // while a rescan's new kinds, streamed in after the view moved, were compiled
      const warmBusy = warming.length > 0 || warmPending > 0 || now - lastWarmWork < 1500;
      if (overlaid) {
        overlayShown = true;
        if (!overlay.valid || !overlay.fits()) { overlay.capture(); captured = true; }
        // (a picture that left something out: no frame this time, the next one makes it again)
        if (overlay.valid) lazily(overlay.draw); else { lastWaveFrame = now; return; }
      } else if (settledAO) { freezeAO(true); lazily(renderSettled); freezeAO(false); } else lazily(renderPlain);
      presented(now);
      animRestUntil = Infinity;                     // (until this frame is done)
      logFrame(now, 'animating').then(({ ms }) => {
        animCost = ms;
        const slow = ms > ANIM_SLOW_MS;
        if (!captured && !(slow && warmBusy)) animSlowRun = slow ? animSlowRun + 1 : 0;
        if (animSlowRun >= 2 && ANIM_BY_FRAME) {
          animSlow = true; animSlowMs = ms;
          animSlowRun = 0;
        }
        animBusy += ms;
        animRestUntil = performance.now() + (ANIM_BY_FRAME ? ms * ((performance.now() - lastInput) / 1000 < WAVE_SLOW_S ? 0.5 : 2) : ms);
      });
      statsFrame(now, `${animWhat} `);
      return;
    }
    waveClock = now;
    statsIdle(now);
    return;
  }
  // a change of light held under the cover, the view still: its passes prepared without drawing (see heldRound)
  if (hold !== null && !moving && (lastGaps || heldFresh) && heldRound(now)) return;
  dirty = viewDirty = false;
  if (overlay) overlay.valid = false;            // (any other frame: the overlay's picture of the city made again)
  if (!moving) overlayShown = false;            // (a settled redraw)
  frameGaps = false;
  frameBuildDeadline = 0;
  frameLinks0 = linksMade;
  glBusyAtFrame = glBusy(now);
  updateEnv();                                 // (a change of light's sky map, made once, before this frame)
  tickWater(now, animate);
  updateSun(shadowDirty && !moving);
  // haze sits in the lowest kilometre or two: looking down from higher up, the line of sight crosses
  // less of it, so the density falls with the camera's altitude
  scene.fog.density = HAZE_DENSITY * settings.haze * Math.min(1, HAZE_LAYER / Math.max(camera.position.y, 1));
  // (city.json night.highExposure [h0, h1, k], opt-in, Tokyo M8 fix round 1: after dark the exposure times up to k for a
  // camera between h0 and h1 m up, as a night photo from the air is exposed for the lit plain, not for the street)
  if (HIGH_EXPOSURE) {
    const [h0, h1, k] = HIGH_EXPOSURE;
    // (with the dusk grade, night.duskGrade, half of it comes with the lights and half with the night's depth (cityGlow:
    // full from 9 degrees down): at Hong Kong's dusk the whole of it had doubled the blue sky light over the city, and
    // with none of it the blue hour from the air was darker than the night)
    const depth = night.grade ? night.state.lights * (0.5 + 0.5 * night.u.cityGlow.value) : night.state.lights;
    renderer.toneMappingExposure = EXPOSURE * nightExposure * (1 + (k - 1) * THREE.MathUtils.smoothstep(camera.position.y, h0, h1) * depth);
  }
  night.u.hazeK.value = settings.haze;             // (the night's glowing haze follows the slider too)
  shadowDirty = false;
  cullTiles();
  trees.update(moving);
  rooftops?.update(moving);
  cars.update(waveTime, moving);
  // the city around the target for glass to reflect, re-captured only when the settled view has moved on
  // or the light changed (the water's mirror is drawn for the main camera, so it is off meanwhile)
  // (when a shadow map is due, the capture draws it first instead of keeping the old one: on a jump updateSun
  // has just moved the shadow camera, and when the last tiles came in the old map lacked them, so the old map
  // shaded the streets in the wrong places and the reflection at a tower's foot differed by where the view
  // came from; trees, rooftops and cars are hidden while it captures, so the view then draws a map of its own)
  const shadowsFor = (draw) => { const due = sun.shadow.needsUpdate; draw(); if (due) sun.shadow.needsUpdate = !night.state.moon; };
  // (facade.probe.glassOnly: only with glass in view, else the last capture kept or dropped; and a moving frame that
  // brings glass into view with no capture to show captures first, so glass never shows without the city in it)
  const probeView = camera.position.distanceTo(controls.target), probeGround = terrain.height(controls.target.x, controls.target.z);
  if (settings.cityMirror && probeReady && (firstShown || !LOADING.passesLater) && (!moving || probeJump || (PROBE.glassOnly && cityReflection.empty))
    && cityReflection.due(controls.target, probeView, probeGround)) {
    if (!PROBE.glassOnly || glassInView()) lazily(() => shadowsFor(() => cityReflection.update(scene, controls.target,
      probeView, { ...probeOptions(), before: () => setWaterReflection(false) })),
      () => cityReflection.markStale());
    else if (!moving || probeJump) cityReflection.skip(controls.target, probeGround);
  }
  probeJump = false;
  // the city mirrored in the water (water.js), drawn before the view that shows it
  if (settings.mirror) lazily(() => afterShadows(() => renderWaterReflection(renderer, scene, camera, { hide: [sky, cars.group], moving })));
  // moving: the plain forward render; settled: one frame with ambient occlusion and MSAA
  // (from far above there is nothing for occlusion to add, so skip its passes)
  settledAO = !(moving || !settings.ao || camera.position.distanceTo(controls.target) > 6000);
  updateGlow();
  // (city.json shadows.fit: the tiles that can't shadow anything in view left out of this frame's shadow map)
  if (shadowTrim && sun.shadow.needsUpdate && sun.castShadow) shadowTrim.cull(camera, tileGroups, { mirror: settings.mirror, target: controls.target });
  try {
    lazily(settledAO || (moving && (glowing ? !glowMovingReady : !plainReady)) ? renderSettled : renderPlain);
  } finally { shadowTrim?.restore(); }
  // (after the view: what is left of the frame's build budget)
  if (moving && glowing && !glowMovingReady) prepareMovingGlow(true);
  // a complete frame is copied for a later change of light's cover (so the change needn't draw the old light
  // again: at the overview that first plain render built every render object, a 0.5 s task), moving frames
  // too, at their lower resolution (a light switched just after a move)
  if (hold === null && !frameGaps) keepFrame();
  lastGaps = frameGaps;
  presented(now);
  if (toFree.length) freeUploaded();
  const logged = logFrame(now, moving ? 'moving' : 'settled');
  for (const waiting of filmWaiters.splice(0)) waiting(logged);
  if (!drawnTotal) logged.then(() => {
    performance.mark('first frame');
    firstShown = true;
    loadingEl.classList.add('streaming');
    showProgress();
  });
  lastWaveFrame = lastDrawnAt = now;
  statsFrame(now, '');
});

// leaving the page (a reload, another page): the GPU's memory handed back at once, the device destroyed (WebGPU)
// or the context lost (WebGL 2). Left alone, a page going into the back-forward cache kept its 2-2.5 GB of
// render targets and buffers in the GPU process until evicted, minutes later, and every load in a tab added
// another (Paris M9: `free`'s shared memory, which destroying the device returned at once). A page brought back
// from that cache loads again. (?release=0: not)
if (params.get('release') !== '0') {
  addEventListener('pagehide', () => {
    leaving = true;
    renderer.setAnimationLoop(null);
    const device = renderer.backend.device;
    if (device) device.destroy();
    else renderer.backend.gl?.getExtension('WEBGL_lose_context')?.loseContext();
  });
  addEventListener('pageshow', (e) => { if (e.persisted) location.reload(); });
}

// the menu: places, display settings, controls help (ui.js)
createMenu({
  views: index.views, goTo, settings, invalidate, setSun, city, trees, lightShadows: sun, shadowsOn: () => shadowsOn, setShadows,
  setReflections: (k) => {
    mat.buildings.userData.reflect.value = glassReflect * k;
    if (mat.sea.userData.reflect) mat.sea.userData.reflect.value = waterReflect * k;
    invalidate();
  },
  hasMarkings: !!markingsIndex,
  lamps, hasMasses: !noMasses && index.tiles.some((t) => t.masses),
  rooftops,
  setMirror: (on) => { settings.mirror = on; setWaterReflection(on); invalidate(); },
  setTraffic: (on) => { settings.traffic = on; cars.group.visible = on; invalidate(); },
  groundTrees: mat.green.userData.treesOn,
});
// ---------------------------------------------------------------- filming (demos/<city>/eval/flythrough.mjs)
// A script renders a camera path frame by frame: frame() draws one settled frame at once (fresh shadows, the
// glass's city captured again, no wait for the view to settle) and resolves once the GPU has finished it; waves
// and traffic take their time from setClock(), so a frame that takes a second to draw moves the water by a
// thirtieth of one; prime() flies the path once so what streams by distance is cached and the shaders built.
let filmClock = null;
const filmWaiters = [];
const film = {
  hide() { document.getElementById('menu').style.display = 'none'; statsEl.style.display = 'none'; },
  setClock(seconds) { filmClock = seconds; },
  async frame({ position, target, hour } = {}) {
    controls.enableDamping = false;              // (no damping left over to move the camera between the frames)
    if (target) controls.target.set(...target);
    if (position) camera.position.set(...position);
    controls.maxPolarAngle = Math.PI - 0.01;     // (a path may look up: under a bridge deck; the map's 86 degree
    controls.update();                           // limit lifted the camera above whatever it looked at)
    lastTarget.copy(controls.target);            // (no settling onto the ground: the path is where it is)
    settling = false;
    if (hour !== undefined) {
      const s = sunAt(hour, city.location.latitude, city.sun.declination, city.time.solarShift);
      setSun(s.azimuth, s.elevation, hour, { jump: true });
    }
    cityReflection.markStale();
    for (let tries = 0; tries < 6; tries++) {
      moving = false;
      renderer.setPixelRatio(settings.resolution);
      lastInput = 0; lastDrawnAt = -Infinity; lastChange = -Infinity;
      dirty = true; shadowDirty = true; viewDirty = false;
      const f = await new Promise((resolve) => filmWaiters.push(resolve)).then((logged) => logged);
      if (!f.gaps && freezeEl.hidden) return f;
      await new Promise((r) => setTimeout(r, 100));   // (a shader still building: the frame is drawn again once it is)
    }
  },
  async prime(path) {
    const p0 = camera.position.clone(), t0 = controls.target.clone();
    // (the start last, once more: what streams by distance was dropped again while the sweep went on)
    for (const [x, y, z] of [...path, ...path.slice(0, 4)]) {
      camera.position.set(x, y, z);
      controls.target.set(x, y - 1, z + 1);
      cullTiles();
      trees.update(false);
      rooftops?.update(false);
      cars.update(waveTime, false);
      await new Promise((r) => setTimeout(r, 250));
    }
    camera.position.copy(p0);
    controls.target.copy(t0);
    controls.update();
    const t = performance.now();
    while (film.warmLeft() > 0 && performance.now() - t < 120000) await new Promise((r) => setTimeout(r, 250));
    await new Promise((r) => setTimeout(r, 2000));
  },
  warmLeft,
};

// handles for poking at the scene from the browser console
window.__viewer = { invalLog, overlay, glCompletes, animWhy: () => animWhy, animState: () => ({ animSlow, animSlowMs, overlayReady: !!overlay?.ready, overlayValid: !!overlay?.valid, ANIM_FULL, ANIM_BY_FRAME, animSlowRun,
    warming: warming.length, warmPending, sinceWarmWork: Math.round(performance.now() - lastWarmWork) }), city, scene, camera, controls, mat, hemi, sun, moon, renderer, invalidate, pipeline, aoPass, scenePass, trees, cars, rooftops, settings, setSun, waterInView, terrain, night, fogNodes, envSky, finiteSky,
  glow: { settledGlow, stillGlow, movingGlow, GLOW, movingReady: () => glowMovingReady }, warmLeft, drawn: () => drawnTotal, animBusy: () => animBusy, frames: () => frameLog, gpuDone, warmLog, lost: () => deviceLost,
  inFlight: () => inFlight, buildLog, sliderRes: (r) => { SLIDER_RES = r || null; },
  cityReflection, probe: { options: PROBE, glassInView }, coverWater, idle: (s) => { lastInput = performance.now() - s * 1000; }, film,
  // (facadeArgs: what the building material was made with, so a measurement can make a variant in the page and swap it
  // onto the facades: Singapore M9's in-page A/B of facade options; a swapped material skips the glass probe's bookkeeping)
  goTo, views: index.views, shadowTrim, facadeArgs: { createFacadeMaterial, index, envMap, cityReflection, nightU: night.u, facadeStyles, billboards, streetLight: lampsData?.streetLight }, setMirrorCull: (on) => { setMirrorCull(on); invalidate({ redraw: true }); }, mirrorStats,
  massChunks: { count: massChunks.length, set: (on) => { for (const m of massChunks) m.visible = on; for (const m of massWhole) m.visible = !on; invalidate({ redraw: true }); },
    aoCut: (on) => { massAoCutOn = on; invalidate({ redraw: true }); } } };                    // goTo({x, y, z, distance, elevation, azimuth}): a view, its target's height kept; views: the presets

// the view shows once the ground and the blocks around it are in and the shaders of its passes compiled, by
// night too (?nightcompile=0: a view starting after dark prepared by its first frames instead, lazily)
// (city.json loading.deferLayers: the trees, rooftops and cars only once the view is up, hidden till then so that
// no shader of theirs is compiled for it; their first frames prepare them lazily, and they come in a moment later)
const deferred = LOADING.deferLayers ? [trees.group, cars.group, ...(rooftops ? [rooftops.group] : [])].filter((g) => g.visible) : [];
for (const g of deferred) g.visible = false;
const compiled = [];
const nextFrame = () => new Promise((resolve) => requestAnimationFrame(resolve));
// one round of preparing the view's passes: a little at a time, so the page stays responsive (the shadow map's
// shaders too)
const compileRound = (budget) => {
  sun.shadow.needsUpdate = true;
  const r = compileOnly(() => framePasses(!LOADING.passesLater, !LOADING.passesLater), budget, { shadows: true });
  compiled.push(r.ready);
  return r.complete;
};
// (city.json loading.earlyCompile: begun with the ground and the first near blocks, while the rest of them still
// download: the driver compiles in the background meanwhile, and the round once all are in finds little new.
// A round whenever tiles have come in since the last, or the last was cut short)
if (LOADING.earlyCompile && (!night.state.on || NIGHT_AHEAD)) {
  let nearDone = false, seen = 0, complete = true;
  nearLoaded.then(() => { nearDone = true; });
  await groundLoaded;
  while (!nearDone) {
    if (tileGroups.length !== seen || !complete) {
      seen = tileGroups.length;
      cullTiles();
      updateSun(true);
      complete = compileRound(100);
    }
    await nextFrame();
  }
}
await Promise.all([groundLoaded, nearLoaded]);
performance.mark('near in');
loadtext.textContent = 'Preparing the view';
cullTiles();
if (!LOADING.deferLayers) {
  trees.update(false);
  rooftops?.update(false);
  cars.update(waveTime, false);
}
updateSun(true);
// (at most MAX_ROUNDS times)
for (let round = 0; (!night.state.on || NIGHT_AHEAD) && round < MAX_ROUNDS; round++) {
  if (compileRound(200)) break;
  await nextFrame();
}
performance.mark('built');
await Promise.all(compiled);
sun.shadow.needsUpdate = true;
performance.mark('compiled');
// (after dark the moving frames' glow pass was among them, unless loading.passesLater left it for later)
if (NIGHT_AHEAD && night.state.on && !LOADING.passesLater) { glowMovingReady = true; glowPrep = null; }
shown = true;
for (const g of deferred) g.visible = true;
// (loading.passesLater: the first frame is the settled one, whose passes were compiled; a moving one first, then
// the settled one 250 ms later, drew the heaviest frame twice and swapped a soft picture for a sharp one)
if (LOADING.passesLater) viewDirty = false;
// (the arrays of tiles on the GPU dropped while the view is idle too: frames alone, a few parapets' worth each, left
// hundreds of MB of them in the page for as long as nothing was drawn)
setInterval(() => { if (toFree.length) freeUploaded(); }, 200);
// (loading.passesLater: the moving frames' passes prepared once the first frame is on screen, a little at a time
// between frames; the probe captured)
// Glass's city probe first: its passes, the sun's shadow map drawn inside the capture too (a render context of its
// own: another call depth), prepared without drawing before the first capture (probeReady), which until then waits.
// Captured at once, the first capture built them in the second frame on screen: Berlin's Mitte, a 110 ms shadow
// material on top of the capture's own ~170 ms, a 305-308 ms task
if (LOADING.passesLater && !night.state.on) {
  plainReady = false;
  probeReady = !settings.cityMirror;
  const prepared = [];
  (async () => {
    while (!firstShown) await new Promise((resolve) => setTimeout(resolve, 50));
    if (!probeReady) {
      const probePrepared = [];
      for (let round = 0; round < MAX_ROUNDS; round++) {
        await new Promise((resolve) => setTimeout(resolve, 50));
        if (night.state.on || !settings.cityMirror) break;
        sun.shadow.needsUpdate = true;
        const r = compileOnly(() => cityReflection.prepare(scene, controls.target, probeOptions()), BUILD_MS, { shadows: true });
        sun.shadow.needsUpdate = true;
        probePrepared.push(r.ready);
        if (r.complete) break;
      }
      await Promise.all(probePrepared);
      probeReady = true;
    }
    cityReflection.markStale();
    invalidate({ redraw: true });
    for (let round = 0; round < MAX_ROUNDS; round++) {
      await new Promise((resolve) => setTimeout(resolve, 50));
      const r = compileOnly(() => renderer.render(scene, camera), BUILD_MS);
      prepared.push(r.ready);
      if (r.complete) break;
    }
    await Promise.all(prepared);
    plainReady = true;
    performance.mark('moving compiled');
  })();
}
invalidate({ shadows: true, redraw: LOADING.passesLater });
pumpBlocks();                                    // (the late blocks, if only they are left)
// the backdrop's land cover maps (06e_masses), the lowest priority: once the view is up
if (index.cover) {
  const tl = new THREE.TextureLoader();
  const prep = (tex) => { tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8; return tex; };
  Promise.all([tl.loadAsync(TILES + index.cover.file), index.cover.inner ? tl.loadAsync(TILES + index.cover.inner.file) : null])
    .then(([outer, inner]) => {
      setCover(prep(outer), index.cover, inner && prep(inner), index.cover.inner);
      invalidate({ redraw: true });
      // the line map (roads, rail beds and the tracks' direction: data, linear, no mipmaps' blur of the direction)
      const lines = index.cover.inner?.lines;
      if (lines) {
        tl.loadAsync(TILES + lines.file).then((tex) => {
          tex.colorSpace = THREE.NoColorSpace; tex.anisotropy = 8;
          setCoverLines(tex);
          invalidate({ redraw: true });
        }).catch((e) => console.warn('city: cover lines failed', e));
      }
    }).catch((e) => console.warn('city: cover map failed', e));
}
// the loading screen gives way to a small progress bar at the bottom once the first frame is on screen (the
// loop: drawn, and the GPU done with it)
// the day's and night's shaders held and compiled from now on while the view is idle (warmSteps): begun
// as soon as the view is up, since most of the time goes into the driver's compiler, which works in the
// background (what loads after has its shaders prepared as it is first drawn)
warming = warmSteps();
// then the rest: seawalls, revetments, beaches, mudflats, river and pond banks, pools (05e_shores.py; web/shores
// links to ../../data/<city>/shores; the viewer runs without them if the folder is missing), and the woods'
// far carpet (trees.js)
const shoresLoaded = loadShores(loader, params.get('shores') ?? 'shores/', { sunDir, pool: city.shores?.pool, quayGrass: city.shores?.quayGrass, pondBank: city.shores?.pondBank }).then((g) => {
  if (g) { scene.add(g); probeShores = g; invalidate({ redraw: true }); }
});
trees.loadCarpet();
await Promise.all([cityLoaded, shoresLoaded]);
performance.mark('all in');
loadingEl.remove();
cityReflection.markStale();                    // all tiles in: capture the city again
invalidate({ redraw: true });
window.__ready = true;
