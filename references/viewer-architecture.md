# Viewer architecture

The viewer is an engine shared by every city, `engine/viewer/` in this skill: `index.html` plus ES modules,
three.js from a pinned CDN, no build step, no bundler, no npm. A city's `demos/<city>/web/` holds only its
`city.json` (title, About, sun, wind, conventions...), a tracked link `engine` to the engine folder, `index.html`
as a tracked link to the engine's page, and git-ignored links to its data, so `web/` alone can be served by
`python3 -m http.server` (which follows the links). `engine/viewer/README.md` has the module map, every
`city.json` key with its default, and how to start a city's `web/` folder; worked `city.json` files of seven
cities are in `../examples/<city>/web/`.
Module paths below are the engine's.

Companion docs: `materials-and-realism.md` (what each material does), `performance-and-loading.md` (budgets,
streaming, shader compilation), `tsl-and-three-pitfalls.md`, `testing-and-tooling.md`.

## 1. Bootstrap: import map, cache busting

```html
<script type="importmap">
{ "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.186.1/build/three.webgpu.js",
    "three/webgpu": "https://cdn.jsdelivr.net/npm/three@0.186.1/build/three.webgpu.js",
    "three/tsl": "https://cdn.jsdelivr.net/npm/three@0.186.1/build/three.tsl.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.186.1/examples/jsm/"
} }
</script>
<!-- a fresh query string on every load, passed on to main.js's own imports -->
<script type="module">import(`./main.js?v=${Date.now()}`);</script>
```

- **Pin the exact version** (0.186.1). `main.js` patches three internals (shader preparation, see
  `performance-and-loading.md`); any upgrade must re-check those hooks. Map both `three` and `three/webgpu` to
  `three.webgpu.js` so addons importing `three` get the same module instance.
- **Cache busting.** `python -m http.server` sends no cache headers, so browsers kept stale modules after edits
  (the user saw old code after reloads). `main.js` imports every sibling with its own query string:
  `const { createTrees } = await import(\`./trees.js${new URL(import.meta.url).search}\`);`
  Only `index.html` itself needs a hard reload (⌘⇧R) after it changes; tell the user when it does.
- `index.html` holds all CSS and markup: `#menu` (collapsible panel), `#stats`, `#loading` (+ `#bar`), `#note`,
  and `<canvas id="freeze">` (the cover used during a change of light). Colours as CSS variables; system font.

## 2. Renderer, camera, scene frame

```js
// reversed float depth on WebGPU; logarithmic only on WebGL 2 (Paris M9: see the depth note below)
const renderer = new THREE.WebGPURenderer({ antialias: true, reversedDepthBuffer: webgpu, logarithmicDepthBuffer: !webgpu });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = THREE.NeutralToneMapping;   // Khronos PBR Neutral: ACES shifted hues and crushed the haze
renderer.toneMappingExposure = 0.9;                // x (1 + 0.75) at night (night.js)
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
await renderer.init();                             // falls back to WebGL 2 by itself without WebGPU
const backend = renderer.backend.isWebGPUBackend ? 'WebGPU' : 'WebGL 2';   // shown in the stats line
const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 2, 120000);
```

- **Units and axes:** 1 unit = 1 m; x = east, z = south (north is −z), y up; origin = the pipeline's projected
  origin (UTM). A `compass(azimuthDeg, elevationDeg)` helper converts compass directions to scene vectors; use it for
  sun, moon, camera presets.
- **Reversed float depth** (WebGPU) because the scene spans 2 m to 120 km (city + 36 km terrain backdrop + 400 km
  sea plane). It was a logarithmic depth buffer until Paris M9, and that one's cost was far bigger than thought: its
  fragment depth writes turn off early-Z, so every wall behind the front one runs the full facade shader. Switching
  to `reversedDepthBuffer: true` cut Avenue de l'Opéra at night from 1,053 to 212 ms and by day from 509 to 155 ms
  (Iris Xe, 1600×1000 at 2×), the overview by day 376 → 248 ms. Depth-based effects convert with
  `perspectiveDepthToViewZ` (reversed-aware) or `logarithmicDepthToViewZ` on WebGL 2, where reversed depth needs
  `EXT_clip_control` and the viewer keeps the log buffer (`?depth=log` forces it on WebGPU for comparisons).
- **Everything real-world is baked in the pipeline** (heights on the terrain, quantized positions, per-vertex
  facade data); the viewer only places what it invents itself (trees on the terrain, the orbit target, the camera).

### Scene composition (what `main.js` adds, in draw order where it matters)

| Object | Notes |
|---|---|
| `SkyMesh` (addons) | `scale 200000`, turbidity 6, rayleigh 1.6, mieCoefficient 0.006, mieDirectionalG 0.8, cloudCoverage 0.55, cloudDensity 0.55; `renderOrder = -2`; night extends its colour node (night.js) |
| Sea plane | `PlaneGeometry(400000, 400000)` at y = −1, **depthless backdrop**: `depthWrite = false`, `renderOrder = -1` |
| Hemisphere light | sky `0xc4d6e8`, ground `0x7a705e`, 1.1 by day, blended to night colours after sunset |
| Sun | `DirectionalLight(0xfff1dc, 4)`, shadow 2048², near 10, far 12000, bias −0.0004, normalBias 1.5, `shadow.autoUpdate = false` (throttled, `performance-and-loading.md`) |
| Moon | a second `DirectionalLight(0xa8bcff)` without shadows, sharing the sun's target; visible only when the sun is > 2° below the horizon |
| Fog | `FogExp2` with HDR colour (1.05, 1.18, 1.35), density 7e-5 × haze slider × min(1, 1500 / camera.y), plus a custom `scene.fogNode` (far haze thinning with height; a night variant) |
| Environment | a second `SkyMesh` (`envSky`, scale 50, sun disc off) in its own `envScene`, `pmrem.fromScene(envScene, 0, 0.1, 100, { renderTarget: envTarget })` re-rendered **into the same target** whenever the sun moves, so every material sampling it follows |
| Ground | `tiles/ground.glb`: one mesh per layer, material chosen by glTF material name, lifted by `LAYER_Y` (land 0, mud −0.5, green 0.6, water 0.9, aeroway 1.2; roads are baked at 1.5, markings +0.12 above roads) |
| Building tiles | 1 km glTF tiles; each mesh's material by name (`buildings`, `road`, `bridge`); tile groups tagged `userData.tile = {x, z, size}` for distance culling |
| Markings tiles | same keys, `mat.markings`, no shadow casting, `userData.noReflect` |
| Trees, rooftops, cars | groups owned by their modules, streamed and instanced by distance |
| Shores | `shores/shores.glb`, loaded after the view is up |

Shadow policy: buildings, bridges, land/green/aeroway (hills) cast; roads and markings don't (flat); everything
receives except the backdrop (beyond the shadow frustum). `userData.noReflect = true` on anything flat that the
water mirror would only see from below (ground layers, roads, markings).

## 3. On-demand rendering

**Nothing is drawn while nobody touches the view** (stats line reads `idle · WebGPU`). This was the first heat fix
and is non-negotiable (the page originally redrew the whole city at 60 fps while idle; a MacBook's fans spun up).

State and the one entry point:

```js
let dirty = true, viewDirty = true, shadowDirty = true, moving = false, lastChange = 0;
// redraw: only to draw what was left out for want of a shader: the view hasn't changed, so it keeps its state
const invalidate = ({ shadows = false, redraw = false } = {}) => { dirty = true; viewDirty ||= !redraw; shadowDirty ||= shadows; };
controls.addEventListener('change', () => invalidate());
```

Everything that changes the picture calls `invalidate()`: camera changes, menu switches (`{shadows: true}` when
shadow casters change), a tile arriving (`{shadows: true}` for building tiles), a sun change, a shader becoming
ready (`{redraw: true}`).

### Frame kinds

| Kind | When | What it does |
|---|---|---|
| **Moving** | `dirty && viewDirty` | `setPixelRatio(movingResolution)`; plain forward render (or the single-sample glow pipeline at night); shadow map refreshed at most every 100 ms; trees/rooftops/cars refill at most every 150 ms; water mirror at reduced size |
| **Settled** | 250 ms after the last view change | full resolution, fresh shadow map, glass city probe re-captured if stale, water mirror, SSAO pipeline with 4× MSAA (skipped when the camera is > 6 km from the target), bloom at night |
| **Redraw** | `dirty && !viewDirty` | draws what was left out because its shader wasn't ready, **in the view's current state** (moving or settled). Treating these as view changes made every switch flicker between moving and settled quality |
| **Animation** | settled, nothing dirty, waves or traffic in view | one scene pass reusing the shadow map, the mirrored city and the last settled AO (pre-pass and SSAO frozen); cars and water time advance |
| **Idle** | otherwise | nothing; by day, idle time also runs the background shader warm-up (no frame drawn) |

Loop skeleton (`renderer.setAnimationLoop`, simplified from `engine/viewer/main.js`):

```js
if (!shown) { /* loading: no drawing; every 100 ms cull tiles and let trees/rooftops/cars stream */ return; }
if (controls.update()) invalidate();                   // damping easing out
if (dirty && followGround()) invalidate();             // orbit target settling onto the terrain
if (dirty && viewDirty) { if (!moving) { moving = true; renderer.setPixelRatio(settings.movingResolution); } lastChange = now; }
else if (dirty) { /* redraw: keep state */ }
else if (moving && now - lastChange > 250) { moving = false; renderer.setPixelRatio(settings.resolution); dirty = shadowDirty = true; }
else if (idleByDay && warmupLeft) { warmStep(); return; }   // background shader preparation
if (!dirty) { if (animate && !moving) drawAnimationFrameThrottled(); return; }
dirty = viewDirty = false;
updateSun(shadowDirty && !moving); cullTiles(); trees.update(moving); rooftops.update(moving); cars.update(t, moving);
if (!moving || probeJump) lazily(() => afterShadows(() => cityReflection.update(...)));   // glass probe: when stale, or on a jump to a place
if (settings.mirror) lazily(() => afterShadows(() => renderWaterReflection(...)));
lazily(settledAO ? renderSettled : renderPlain);
presented(now);                                        // cover logic during a change of light
```

### Animation policy (waves and traffic)

- Animate only while: (Waves on **and** water within 5 km fills ≥ 4 % of a 25×25 ray grid of the view — cached
  while the camera is still) **or** (Traffic on **and** moving cars on lanes within 1.5 km); **and** the tab is
  visible; **and** there was input in the last 180 s.
- Rate: **24 fps**; **12 fps after 30 s without input**; **stopped after 180 s** (the view keeps its last frame).
  Slots on a fixed beat so 60 Hz displays average 24: `lastWaveFrame = Math.max(lastWaveFrame + 1000/fps, now - 1000/fps)`
  and skip when `now - lastWaveFrame < 1000/fps - 4`.
- Water and traffic share one clock that only advances while frames are drawn (`dt` capped at 100 ms), so nothing
  jumps after a pause.
- **What counts as input:** `pointerdown`, `wheel`, `keydown`, `input` (menu) listened in the capture phase and
  passive, plus the controls' `change`. **Not `pointermove`**: hovering kept the loop at 24 fps.
- Water had to fill 4 % of the view (first 1 %): a distant river sliver kept the loop running.
- The stats line says what animates (`waves + traffic 24 fps`), else `idle`. When the user asked "traffic is off
  and I'm not moving, why isn't it idle?", the answer was the waves; the label now makes that visible.

### Resolution

`settings.resolution = min(devicePixelRatio, 2)`; `settings.movingResolution` the same by default. History: moving
frames went 1× → 1.5× → 2× because the user saw softer shadows/edges while moving, and once rendering was on demand
with throttled shadows the fans stayed quiet at 2×. Keep a URL escape hatch (`?moving=1.5`) and the menu's
Resolution choice (1, 1.5, 2 up to the screen's dpr) for hot machines.

## 4. Camera and controls

- `MapControls` with damping; `maxPolarAngle` 86°, `minDistance` 30 m, `maxDistance` 60 km.
  A preset under 4° of elevation is lifted to 4° (London's "Canary Wharf from Greenwich Park" at 0.75° over 3.3 km
  sat ~230 m up, not on the hill): an eye-level view from a hill puts its target a few hundred metres ahead, lowered
  under the eye line (negative lift) so the camera aims 4.2-4.6° down; the far skyline still sits in the upper half.
- **Presets** come from the pipeline (`tiles.json` `views`: `{name, group, x, z, y?, distance, elevation}`); groups
  `Areas` and `Landmarks`. A landmark is framed from its footprint and height with the target a third of the way up
  from its base. `goTo(v)`: target at `(x, v.y ?? terrain.height(x, z), z)`, camera from
  `compass(200°, elevation) * distance` — south-south-west of the target so the afternoon sun (azimuth 225°) lights
  the facades you see. Adapt the azimuth to the city's latitude/hemisphere.
- URL: `?view=<name>` or `?at=x,z,distance,elevation` (any spot; the standard way tests move the camera).
- **Trackpad mode** (default on everywhere, remembered; it used to be on only when `navigator.userAgent` matched `/Mac/`, which left Windows and Linux laptop users with a scroll that zoomed): a `wheel` listener in the
  capture phase with `{passive: false}` that `preventDefault()`s and `stopImmediatePropagation()`s:
  - `e.ctrlKey` (pinch) → return early, let the controls zoom;
  - plain two-finger scroll → orbit: `theta += deltaX * 0.004`, `phi = clamp(phi + deltaY * 0.003, 0.05, maxPolar)`
    (directions reversed after the user tried them: match macOS natural scrolling as used in practice);
  - shift + scroll → pan along the ground, scaled by `0.0015 × distance`.
  - a mouse wheel still zooms: each burst of wheel events (a new one after a 250 ms gap) is judged by its first
    event, mouse when `deltaMode` is not pixels (Firefox) or `|deltaY| >= 50` with no `deltaX` (a notch; Mac
    mice report small accelerated steps and stay in trackpad mode, as before); so trackpad mode can be on by default everywhere.
  Mouse mode: wheel zooms. Always: drag pans, ⇧/⌘-drag or right-drag rotates. Say so in the menu's Controls help —
  the first trackpad complaint was simply that rotation was undiscoverable.
- **Orbit target follows the terrain** (`followGround`, only on frames drawn anyway): once the target has moved
  horizontally, ease `target.y` and `camera.y` together by 30 % per frame towards `terrain.height(x, z)` until
  within 5 cm; keep the camera ≥ `terrain.ceiling(x, z, 15 m) + 10 m`.
  - **A lifted target goes down the line of sight instead.** A place button aims part of the way up its landmark
    (New York's WTC view at 210 m). Easing that target down with the camera dropped the camera 200 m in the
    first frames of the next drag (436 → 229 m in four steps, the tower jumping 244 px for 40 px of mouse): the
    view lurched before following the pointer. A target more than 25 m above the ground now moves along the
    camera's line of sight to where it meets the terrain (a few fixed-point steps; only within 20 km), the
    camera staying put: the picture doesn't change and the drag follows the pointer. Panning over hills eases
    as before.
- `terrain.js`: loads the TIN (`terrain.glb`, quantized positions undone with the node matrix), builds a bucket grid
  of 160 m cells (≈100 ms for ~0.6 M triangles), `height(x, z)` tries the last hit triangle first then its cell's
  (≈6,000 lookups/ms), `ceiling(x, z, r)` = highest vertex within r. Returns 0 beyond the TIN (sea).

## 5. Menu (`ui.js`)

Built on the markup in `index.html`; `main.js` passes in what it may change:
`createMenu({ views, goTo, settings, invalidate, setSun, sun, trees, lightShadows, setReflections, hasMarkings,
rooftops, setMirror, setTraffic, groundTrees })`.

- **Places:** one chip per view, grouped (Areas / Landmarks), active one highlighted. The user asked to drop the
  whole-region button, add landmarks, and make the menu collapsible, compact and prettier.
- **Display switches** (3-column grid of `aria-pressed` buttons): Trees, Rooftops, Shadows, Occlusion, Markings,
  Mirror, Waves, Traffic, Glow, Stats. Hide a switch whose data folder is missing. Tooltips say what each costs
  ("one extra render pass", "redraws 24 times a second while water is in sight").
- **Sliders:** Time 0–24 h (step 0.05, default 15.25, local solar time; `Day` 15.25 / `Dusk` 18.05 / `Night` 21
  shortcuts), Haze 0–300 % (1), Reflections 0–200 % (**0.5 default** — the user's pick after trying it), Resolution
  (segmented 1× / 1.5× / 2×, only up to the screen's dpr).
- **Sun from the hour:** solar elevation/azimuth from latitude and a fixed declination (`city.json`
  `location.latitude`, `sun.declination` or `sun.date`; Shenzhen: 22.54° N, −10°, the clearest season; sunset
  ≈ 17:45, dark ≈ 18:35). Pick the city's photogenic season. The Day/Dusk/Night hours are `time.presets`.
- **Persistence (per browser):** `localStorage` keys prefixed per city (`city.json` `storagePrefix`, e.g. `shenzhen3d.*`): `collapsed` (default
  collapsed: the city first), `open.<section>`, `trackpad`, `stats`, `resolution`. Wrap every access in
  try/catch (private mode). Don't persist view-changing state that should start fresh (time, haze).
- **URL parameters win for the session:**

| Param | Effect |
|---|---|
| `view=<name>`, `at=x,z,d,el` | start view |
| `time=21` | start hour |
| `trees=0 roofs=0 markings=0 ao=0 waves=0 traffic=0 glow=0` | layers/effects off |
| `reflect-water=0` | no water mirror pass; `reflect-city=0`: glass reflects sky only; `reflect=<k>` glass strength |
| `moving=1.5` | moving-frame resolution |
| `blocks=0`, `tiles=<path>`, `shores=<path>` | load separate tile files / alternative data paths |

## 6. Module layout

| Module | Owns | Exports |
|---|---|---|
| `main.js` | renderer, scene, lights, fog nodes, loading/streaming, render loop, AO + glow pipelines, shader preparation (`compileOnly`/`lazily`), background warm-up, change-of-light cover, stats, test handles | — |
| `facade.js` | procedural building material (all styles, glass, landmark skins, night lights), city reflection probe | `createFacadeMaterial`, `createCityReflection` |
| `ground.js` | land, green (parks/woods), aeroway, road, bridge, markings, mudflat, backdrop materials + street lighting | `createGroundMaterials(markingsIndex, { sunDir, night })` |
| `water.js` | sea and inland water materials, shore SDF (`shoreField`), planar mirror, wave motion, `waterInView` | `createSeaMaterial`, `createInlandWaterMaterial`, `shoreField`, `renderWaterReflection`, `setWaterReflection`, `waterInView`, `setWaterTime` |
| `shores.js` | strips along land/water edges (revetment, quay, beach, mudflat, embankment, pond bank/edge, pools) | `loadShores(loader, base, { sunDir })` |
| `trees.js` | leaf atlas, species models, impostor bake, streaming, instancing, far carpet | `createTrees(...) → { group, update, setNear, loadCarpet, stats }` |
| `cars.js` | vehicle models, lanes/queues, parked cars, planar shadows | `createCars(...) → { group, update, active, without, setDensity, stats }` |
| `rooftops.js` | rooftop items (5 prototypes), parapets from building walls | `createRooftops(...) → { group, update, stats }` or `null` |
| `terrain.js` | ground height lookups | `loadTerrain(loader, url) → { height, ceiling, box }` |
| `night.js` | dusk/night sky, moon, light schedule, lit material copies, night haze | `createNight() → { u, extendSky, update, apply, state }` |
| `ui.js` | the menu | `createMenu(api)` |

Conventions that keep modules independent:
- Factories take `{ scene, camera, invalidate, renderer, terrain, night }` and own a `THREE.Group`; the menu toggles
  `group.visible`. `update(moving)` is called on drawn frames only; it streams the module's own 1 km tiles by
  distance (4 requests in flight, nearest first, dropped well beyond reach) and refills instance buffers when the
  camera moved `> max(8 m, 3 % of its height above ground)` or turned > 0.04 rad, at most every 150 ms while moving.
- A missing data folder (fetch of its index fails) returns a no-op object or `null`; the viewer runs without it.
- Materials take `night` (the uniforms from `createNight().u`) or `null` for "never lights up"; lit variants are
  registered with `night.withLights(mat, emissionNode)`.
- Anything a material needs from the frame (camera position, sun direction) is a uniform updated in `update()` or
  via `uniform(...).onRenderUpdate(...)`, never baked at creation (time of day must relight everything).
- Data folders in `web/`: `tiles`, `blocks`, `markings`, `trees`, `shores`, `cars`, `rooftops` — git-ignored
  symlinks into `../../data/<city>/`. The page, `city.json` and the data resolve against the page's URL (the
  city's folder), the modules against the engine's (`./engine/...`).
- Whatever differs between cities comes in as options from `city.json` (`createNight(city.night)`,
  `createGroundMaterials(..., { ground, markings })`, `configureWater(city.water)`, `createFacadeMaterial(...,
  city.facade)`, `createTrees({ classes })`, `createMenu({ city })`), never as a constant in a module.

## 7. Test handles

Keep these; every test and critique relies on them:

```js
window.__viewer = { scene, camera, controls, mat, hemi, sun, moon, renderer, invalidate, pipeline, aoPass, scenePass,
  trees, cars, rooftops, settings, setSun, waterInView, terrain, night, fogNodes,
  glow: { settledGlow, stillGlow, movingGlow, GLOW }, warmLeft: () => warming.length, cityReflection,
  idle: (s) => { lastInput = performance.now() - s * 1000; } };   // simulate s seconds without input
// ... after everything (blocks, shores) has loaded:
window.__ready = true;
```

Useful knobs: `__viewer.trees.setNear(m)` (0 = impostors only), `__viewer.cars.setDensity(k)`,
`__viewer.mat.buildings.userData.tune` (live glass uniforms: `grazing`, `skyDim`, `skyDesat`, `soft`),
`mat.*.userData.nodes` (intermediate TSL nodes to visualise), `mat.sea.userData.reflect/distort/skyLimit`,
`__viewer.warmLeft()` (background warm-up steps left), `renderer.info.render.{drawCalls,triangles}`.
Moving the camera from a test: set `controls.target` and `camera.position`, `controls.update()`,
`invalidate({ shadows: true })`, wait ~4 s for the settled frame.

## 8. Porting notes

- Change: the city's `web/city.json` (latitude and season, time shortcuts, view azimuth, wind, runway heading,
  centre-line colour and dashes, localStorage prefix, title/About text; `engine/viewer/README.md` lists every key),
  and the city's README. Don't copy the engine; extend it (a new species, car model, facade style) so every city
  gets it.
- Keep: the loop, invalidate/redraw semantics, the shader preparation hooks, the module contracts, the test handles.
- Southern-hemisphere cities: the sun is in the north; the engine then looks from the north-north-east and hangs
  the moon in the north-east by default (`camera.azimuth`, `night.moon`); check every other "sun side" assumption (tree crowns, rock facets use the live `sunDir`, so they follow).
