# Performance and loading

What kept a MacBook cool and the page responsive while the first reference scene (Shenzhen) grew to ~7 M triangles,
~100 MB of data and a dozen node materials in five passes, and what each later city's M9 added. Code:
`engine/viewer/main.js` (loop, loading, shader preparation), per-module constants in the other modules. Sections 8–16
are per-city lessons; the measurement scripts they used lived in each reference city's `eval/` and are not part of
the skill: `scripts/speedtest.mjs`, `scripts/pixdiff.mjs` and the in-page methods of `testing-and-tooling.md` cover
the same ground. Unless noted, numbers were measured on a Linux test machine with an
Intel Iris Xe (WebGL 2; WebGPU where stated) — a slow GPU; the user's Mac is several times faster. Compare
before/after on the same machine, never across machines.

## 1. Budgets

The critic's budget table is in `critique.md`. The viewer-side targets:

| Measure | Target | Shenzhen |
|---|---|---|
| Idle, nothing animating | 0 frames | ✓ (`idle` in the stats line) |
| Animation | 24 fps → 12 fps after 30 s → stop after 180 s | ✓ |
| Draw calls, settled city view | a few hundred | 150–680 main pass by view; night adds ~12 (bloom) |
| Triangles in view | ≲ 3–4 M | 1.5–3.4 M typical |
| Usable view (80 Mbit/s, 30 ms RTT) | ≲ 12–15 s | 12.0 s |
| Everything loaded | ≲ 20–30 s | 18.1 s |
| Longest main-thread stall once usable | ≲ 350 ms | 338–349 ms (WebGL; ~175 ms after warm-up) |
| Change of light after warm-up | no visible wait, 0 shaders built | 0 built, frames 56–89 ms |
| Night-only features by day | 0 cost | lit material copies, separate fog node, bloom off |

## 2. The heat story (first fix, keep it)

The user: "when I drag a bit, my Mac's fan is up and starts getting hot." The viewer redrew the whole city ~60×/s
while idle, at full Retina resolution, re-rendered the shadow map every frame, and drew everything out to 55 km.

| Measure | Effect on the picture | Kept? |
|---|---|---|
| Draw only when something changes (`invalidate`) | none | yes, the core |
| Reduced resolution while moving, full once settled (250 ms) | softer while moving | went 1× → 1.5× → **2× (same as still)** once the rest kept the fans quiet; `?moving=1.5` escape hatch |
| Shadow map only when the view moved/zoomed enough, and once on settle | shadows froze and jumped while moving ("shadows are less natural") | refined: also every **100 ms** while moving |
| Skip tiles beyond a view-dependent radius (fog hides them) | none visible | yes |

Then the user asked "what did you do for the heat problem? … the graphics quality decreased": explain each
measure with its visual cost (a table like the one above) and give back quality where it's cheap. After the
refinements: "fans stay quiet … try 2x" → "still quiet".

Later heat sources, each capped: moving water (throttled 24/12/0 fps, only when ≥ 4 % of the view is water within
5 km, not on hover), traffic (only lanes within 1.5 km animate), background shader warm-up (only while idle by day,
≤ 40 ms per 100 ms). Animation frames cost ~14 ms CPU each in the CBD (≈30–35 % of a core) — that's why they stop.

## 3. Per-frame cost levers

### Shadows
- One 2048² PCF map, `shadow.autoUpdate = false`, updated by `updateSun(force)`: frustum half-size
  `clamp(1.2 × camera-to-target distance, 800, 6000)` m around the orbit target; re-rendered when forced (settled
  frame after a change, sun moved, tiles arrived), when the target moved > ¼ of the span, the span changed > ⅓, or
  100 ms passed while moving. `bias −0.0004`, `normalBias 1.5`.
- **By moonlight no shadow pass and no shadow lookups**: the moon is a separate shadowless light, the sun is hidden
  (`visible = false`). Every lit shader sampling the unused sun map cost ~7 % of a night frame. (Turning off
  `castShadow` instead lost the daytime shadows for good — `tsl-and-three-pitfalls.md`.)
- **Never update the shadow map inside the probe or mirror passes** (`afterShadows()` defers a due update to the
  main view): those passes hide trees/rooftops/cars, and a shadow map drawn there lacked their shadows until the
  view moved ("tree shadows gone after switching back to day").
- Cars never cast into the map (planar shadows instead), so traffic never forces a shadow pass.

### Ambient occlusion
Settled frames only (a normals pre-pass + SSAO at half resolution + the MSAA scene pass). Faded out 3–6 km (depth via
`perspectiveDepthToViewZ`, or `logarithmicDepthToViewZ` on WebGL 2) and **skipped entirely when the camera is > 6 km from the target**: it drew horizontal
bands across distant views. Animation frames reuse the last AO (pre-pass and SSAO `updateBefore` replaced by no-ops),
with cars emptied from the pre-pass so no dark halos stay where cars were.

### Reflection passes
- Glass city probe: only when stale (moved > max(300 m, ⅕ view distance), sun changed, loading finished); 6 × 256²
  views of tiles within 3.5 km, trees/rooftops/cars hidden; ≈280 draws, 6.2 M tris (half of it the whole-region
  ground and shores, which can't be cut to the radius), 20–30 ms CPU. Never while moving, idle or animating.
  - **Lighter captures (`facade.probe.lean`, Paris, London, Berlin)**: the region-wide ground layers were the bulk of
    a capture (every face drew each whole: 2.5 M triangles a face in Paris), not the buildings. Their triangles are
    sorted into 1 km cells (row order) as they arrive and a copy over the same buffers draws only the rows of cells
    within 4 km (one group per row, ~90 more draws); the shores, town masses, markings and lamps are left out and the
    building tiles cut to 2 km (nearest point). Capture frame against settled, 3200 × 2000, WebGPU: Paris La Défense
    27.7 → 12.1 M triangles (settled 8.3), +33 → +11 ms GPU; London The City 24.5 → 14.1 M (9.2), +34 → +21 ms;
    Berlin Potsdamer Platz 22.6 → 14.7 M (8.9), +27 → +12 ms. The towers' reflections are unchanged within a few levels
    (the probe's own blur hides what lies beyond 2 km).
  - **Only with glass in view (`facade.probe.glassOnly`)**: the capture waits while no glass covers a share of the
    screen (each tile's glass-style wall area from its arrays, at its box's nearest point). Most views of these cities
    hold some glass-style walls (London and Berlin's offices are spread everywhere; Berlin's scattered glass goes pale
    when it mirrors the sky map instead of a capture, so even 0.03 % of the screen counts); it skips in the Marais-like
    glass-free views only. A moving frame that brings glass into view with no capture to show captures first.
- Water mirror: only the screen rectangle where water shows, ≤ 560 lines (moving ≤ 320), tiles ≤ 9 km (moving
  4.5 km), flat meshes (`noReflect`, bbox height < 0.5 m) and cars skipped, no pass without water in view.

| Water mirror cost (WebGL, headless) | Draws | Triangles | Target |
|---|---|---|---|
| Main pass, for comparison | 150–680 | 2.1–3.4 M | — |
| Mirror, settled | 96–180 | 0.9–1.6 M | 704×448 |
| Mirror, moving | 46–59 | 0.76–1.2 M | 512×320 |

### Culling and levels of detail

| Layer | Distances | Draw calls |
|---|---|---|
| Building/markings tiles | hidden beyond `min(60 km, 9 km + 3 × view distance)` from the camera; markings also by switch | ≈1 per material per visible tile |
| Trees | cards < 280 m (45 m dithered fade), impostors to 4.5 km (600 m fade), dense stands thinned beyond 1.3 km, carpet beyond | 7 species + 1 impostor mesh (+ carpet) |
| Cars | models < 320 m, boxes < 3 km (500 m fade), animated lanes < 1.5 km, planar shadows < 1 km; tiles loaded < 4.2 km, dropped > 5.6 km | ≤ 9 |
| Rooftops | small 420 m, tanks/parapets 900 m, boxes 1.6 km, large 2.6 km (fade over the last fifth) | 6 |
| Shores | strips | 3 (one transparent) |
| Occlusion | faded 3–6 km, skipped > 6 km camera distance | 2 passes + blur |

Per-module refills (instance buffers rewritten from loaded tiles in the frustum) only when the camera moved
`> max(8 m, 3 % of its height above ground)` or turned > 0.04 rad, at most every 150 ms while moving; cars also
rewrite only the animated lanes' instances each animation frame (`addUpdateRange` from the static count).

### Measured effects

Trees (leaf cards + impostors vs the old solid three-LOD trees), triangles in the same views:

| View | Before | After |
|---|---|---|
| Park, 260 m | 1.24 M | 0.56 M |
| Street, 180 m | 0.81 M | 0.36 M |
| Close, 70 m | 1.52 M | 0.65 M |
| Forest, 1.2 km | 2.54 M | 0.23 M |
| Bay, 3 km | 0.70 M | 0.07 M |

Main risk of card trees is fill rate (4–5 overlapping card layers); `trees.setNear(200)` is the knob.

Cars (WebGL): full/box/shadow counts 0/7,064/0 at the 3 km CBD preset (71 k tris, 1 draw, 0.04 ms per animation
frame) to 358/729/1,087 at 200 m in an urban village (103 k tris, 9 draws, 0.15 ms); a refill after a camera move
0.3–1.3 ms.

Terrain (hills) cost: download 81.5 → ~102 MB, triangles 5.95 → 7.21 M (ground 0.59 → 1.02 M incl. backdrop,
markings 0.59 → 0.98 M, carpet 0.32 → 0.62 M); shores/markings compress half as well once heights vary. The user
accepted this; ask before a +25 % download.

Night (GPU timer queries, WebGL, 1744×970 at 2×, CBD 1.7 km):

| Frame | Before the night rework | After |
|---|---|---|
| Night, settled (glow pipeline) | 230 ms | 224–233 ms |
| Night, moving | 105 ms | 102 ms |
| Day, settled | 206 ms | 200 ms (unchanged code) |
| Day, moving | 136 ms | 134 ms |

A settled night frame costs ~10 % more than the same view by day; **moving night frames are cheaper than day** because
they skip multisampling. First night build: settled frames +15–20 %, animation 19 fps instead of 24; per-vertex
per-building values and branch-gated rare terms brought it back.

**The facade uber-shader: branch what most pixels don't show** (Paris M4, WebGPU, Iris Xe, 1600×1000 at 2×). New
facade styles and mansards (+60 shader lines, +28 % triangles) took the settled frame from 291 to 395 ms at the
overview and from 431 to 618 ms at street level. Split it first: swap the building material for a plain physical
one (overview 395 → 204 ms, street 618 → 171), then drop single outputs (`emissiveNode = null`: −88 / −190 ms,
the glass reflection; `colorNode` = vertex colour: −137 ms). So the cost was the fragment shader, not the
triangles, and a branchless (`mix`-everything) shader pays every term on every pixel. Three branches, no look
change (street shot bit-identical, overview within JPEG noise, New York's buildings identical):
- the **glass reflection** (two PMREM lookups, haze and sky grading) only where `openAmount > 0` — solid wall,
  roofs and the stone between windows skip it;
- the **near detail** of ordinary walls (frames, panes, rails, AC units, ironwork, shutters) only where the window
  grid is still resolved (`far < 1`) and not on roofs, curtain walls or patterned skins. The cut is exact (past
  `far = 1` the near term has weight 0), so nothing pops as the view zooms;
- styles the city lacks are a constant `bool(false)` and whole sections (billboards, fire escapes, every wall
  feature of facade/core.js: built only when one of the city's styles lists it in its data, styles.js; roof codes) are
  left out of the graph in JS, so each city's shader carries only its own styles. Float constants are one node per
  value (facade/core.js `float`): a constant is written into the shader, so sharing it costs nothing and spares the
  node builder 15-20 % of the graph; style comparisons stay one per test (shared, each became a variable).
Result: overview 395 → 289 ms settled, 253 → 180 moving; street 618 → 378 settled, 212 → 133 moving; same draws.
Rules for such branches: inside an `If`, rebuild the branch's nodes from `.toVar()` copies taken before it (or from a
function that makes fresh nodes), never reuse a node the rest of the shader also uses, and take every `fwidth`
before it (`tsl-and-three-pitfalls.md` 1, 3, 4); PMREM and `.level()` lookups are fine inside.

**Check that a city's "off" switch is really off, in its own shader** (New York, WebGL 2, Iris Xe, Oct). New York's moving
frames at Downtown Brooklyn crept from 108 to 128-132 ms over the Paris build with the same draws and triangles. A
per-part split (hide each material type while moving) put ~20 of the 24 ms in the building material; bisecting
engine copies on a fixed camera path named the Paris facade commit (109 -> 160 ms, mostly won back by a later
change that skips styles a city lacks: 115) and the night floodlight change (119 -> 126). The rest was one test:
roof codes were gated on `uvRange.base[1] > 0`, but tiles packed before roof codes carry range 1 (and 0 in uv2.y), so
New York and Shenzhen compiled every mansard term (brisis, dormers, seams, roof materials) into every building pixel.
`> 1`: 128 -> 103 ms, below the old viewer's 108, pixels unchanged. (Lesson, now SKILL.md hard rule 6: gate a
city-only shader path on an explicit config key, never on a data range.) With that gone, the floodlight's
`diffuseColor` term measured nothing (103 vs 104): on this GPU a small addition can cost a lot only because it tips an
already large shader over a register threshold, so measure it in the shader it lands in (compiling the unused flood
spires and gold tower out of New York's lit facade likewise bought nothing, and Berlin's moving frames read 5 % slower
without the gold term: left as they were). To find such things, dump the
city's building shader (`renderer.debug.getShaderAsync(scene, camera, mesh)`, GLSL on WebGL 2) and diff it against an
older viewer's, node names normalised: code a city can't use stands out.

**Patterns "on the wall itself" are paid for by every pixel of every wall, and by their sum, not one by one (Singapore
M9).** Singapore's seven on-wall patterns (HDB paint bands, corridor faces, void decks, the five-foot way, shophouse
shutters, colonnades, slab edges: `facade/patterns.js`, each `mix(wall, colour, mask)`) were inline, so the glass towers,
roofs and every other style ran them all. Measured in one load by swapping variants of the building material onto the
facades (`__viewer.facadeArgs`, WebGPU, Iris Xe, 3200 x 2000 settled): all seven left out 160 -> 141 ms at Orchard Road and
176 -> 159 at Marina Bay, but no group alone moved more than noise (the shophouse pair ~5-10, the HDB trio ~3, temples,
worship and roof codes nothing): the size of the shader, not any one term (the register threshold of New York's roof codes
above). Each pattern in an `If` on its own mask, inputs copied (`facade.patternBranch`): 144 ms and 166-170, at night
249 -> 206 (Orchard) and 216 -> 160 (Chinatown street), WebGL 2 451 -> 386 and 816 -> 691 at Orchard; pixels the same.
The night overhead blamed on 13 per-pixel landmark glows was mostly these patterns too (the glows ~5-10 ms of 250;
`night.glowBranch` puts each in an `If` on its circle). Two traps in the in-page A/B: a material swapped onto the facades
skips the glass probe's bookkeeping (main.js keys glass tiles by `mat.buildings`), so compare two swapped variants, never
a swapped one against the original (12 levels brighter windows at Orchard, 0-1 level between two swapped ones); and the
first timing after a swap includes compiling, so time each variant twice in A B B A order.

**Early-Z first: a logarithmic depth buffer shades all the overdraw (Paris M9).** Night cost 1.66× day at the
overview and 2.24× in the street; the M8 profile blamed the facade's night emission (lit windows ~67 ms, shops + wash
~69 at dpr 1) and the plan was to make it cheaper. A split by material (hide each material's meshes in-page, one
load) showed the buildings were 875 of the street's 1,052 ms at night, but a depth-only pre-pass of the buildings
changed nothing: the viewer's `logarithmicDepthBuffer` writes every fragment's depth from its shader, which switches
off early-Z, so each wall behind the front one (1 km tiles, courtyard blocks, triangles in any order) ran the whole
facade shader. `reversedDepthBuffer: true` (float depth, same precision from 2 m to 120 km) on WebGPU:

| Iris Xe, 1600×1000 at 2×, settled (moving) GPU ms | before | after |
|---|---|---|
| Avenue de l'Opéra, day | 509 (181) | 155 (66) |
| Avenue de l'Opéra, night | 1,053 (268) | 219 (77) |
| Overview, day | 376 (235) | 248 (155) |
| Overview, night | 632 (168) | 422 (119) |

Night over day: street 2.07× → 1.41×, overview 1.68× → 1.70×. Lessons: (1) before optimising a shader's terms, check
whether early-Z works at all (a depth pre-pass that changes nothing is the tell); (2) any node writing depth
(`depthNode`, log depth) makes the whole material pay its overdraw; (3) the sky writes no depth, so depth-reading
passes must treat the reversed clear value (0) as background: SSAO only skips depth 1 and drew a faint seam across
the sky until `aoTex` was forced to 1 there.
Also in branches since (all exact, `If` on copies of the inputs, derivatives and texture reads before): the rooms'
lights only where the wall shows a window (the stone between skips them), one hash per floor and zone up close and
the six-hash group blend only where zones are a few pixels, the building's mean share once groups are 16 zones by 8
floors (faded in over the last level, no step); shops one by one only where the ground floor is resolved; roof lamps
their mean once under a few pixels; the ground's rock faces (five octaves on every land, park and backdrop pixel)
only on steep ground; the backdrop's and town ground's unused alternatives (the vertex-colour towns when the land
cover map is on, the painted blocks under the masses) behind their uniform. Worth a few per cent each once early-Z
works; the overview at night is still 1.7× day: the glow (68 ms), the facades' night emission over every roof and
wall of the city (~130 ms) and the lamps (~45 ms) are what is left.

**Town masses (Paris M7 fix).** A ring of low-poly block masses round the modelled districts (06e_masses, 2.8 M
triangles) costs little once it is a handful of draws: merged into 12 km cells it is 7 draws and ~10 ms at the
overview (settled 378.8 ms with it, 368.8 hidden; 873 draws). Put layers that only fill the distance into
**late blocks** loaded after the first usable frame, and secondary textures (the land cover maps) after it too:
usable 15.4 → 14.35 s, 98.5 → 94.9 MB at 80 Mbit/s. **Check a comparison switch drops only what it names**: the
markings tiles were also called `m_<i>_<j>`, so `?masses=0` dropped them with the masses and credited the masses
with 209 draws and 60 ms that were the markings'. Hiding a layer in-page (its material's `visible = false`) is the
cleaner A/B: one load, nothing else changes. And every noise octave in a ground material is paid on every pixel of
it: two extra fbm calls in the town and backdrop materials cost ~30 ms at the overview until folded into one.

## 4. Glow (bloom) without recompiles

`BloomNode` only while `night.state.lights > 0.02`, strength `0.45 × lights`, radius 0.6, threshold 0.7:
- settled: a **second copy** of the AO pipeline whose output adds a half-size bloom of the scene pass;
- still frames without AO: `pass(scene, camera, { samples: 4 })` + half-size bloom;
- moving: `pass(scene, camera, { samples: 0 })` + quarter-size bloom — on this GPU faster than the plain
  multisampled render.
**Switch between prebuilt pipelines; never change one pipeline's `outputNode`** — rebuilding it recompiled the bloom
(~1.2 s) every time the lights came on.

## 5. Loading

### Before/after (WebGL, 1440×900 at 2×, start view the CBD)

| | before, unthrottled | after, unthrottled | before, 80 Mbit/30 ms | after, 80 Mbit/30 ms |
|---|---|---|---|---|
| First frame | 8.0 s (bare ground, tiles popping in) | 10.2 s (near city, final quality) | 9.5 s | 12.0 s |
| View usable | ~26.7 s (+1.7 s frozen first frame) | 10.2 s | ~42.4 s | 12.0 s |
| Everything loaded (`__ready`) | 24.8 s | 14.2 s | 40.8 s | 18.1 s |
| Longest stall once usable | 6.3 s night warm-up + 1.7 s | 338 ms | 6.2 s + 1.5 s | 349 ms |
| Longest stall after background warm-up | – | 174 ms | – | 175 ms |
| Requests / bytes | 1861 / 88 MB | 260 / 62 MB | 1862 / 88 MB | 261 / 62 MB |

(Bytes include three.js from the CDN; visuals identical: mean difference 0.12 levels by day.)

Where the time went before: 3.6–5 s modules and three.js from the CDN; 1.8–3.3 s trees awaited before anything
(carpet decode 0.64 s, atlas, impostor bake 1.2 s); ground + shore field 0.6–0.85 s in one task; ~1,700 small tile
requests (8 s even warm on localhost, 26 s throttled — **request latency mattered more than bytes**; GLTF parsing
1.25 s script, meshopt decode only 0.1–0.2 s); then a 5–6 s night shader warm-up and a 1–1.7 s first settled frame.

### What fixed it
1. **Bundle tiles into blocks** (`07b_blocks.py`): building tiles + markings per **4 km square**, each block one
   file of its glbs back to back, **gzipped** (meshopt streams still shrink by a third), `blocks.json` lists
   `[kind, file, offset, length]` per glb: **91 files, 42 MB instead of ~1,700 files, 67 MB.** Python's
   `http.server` opens a connection per request (HTTP/1.0) and can't compress, so the browser unzips:
   ```js
   async function gunzip(buf) {
     const b = new Uint8Array(buf);
     if (b[0] !== 0x1f || b[1] !== 0x8b) return buf;   // a server may already have decoded it (Content-Encoding)
     return new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
   }
   // then per part: loader.parseAsync(buf.slice(offset, offset + length), '')
   ```
   Fallback without `web/blocks` (or `?blocks=0`): the separate tile files in the same order.
2. **Nearest first:** 4 blocks in flight; the next is always the remaining block nearest the orbit target (the start
   view's until shown), measured as distance from point to square.
3. **Show the view once the near city is in:** loading screen until the ground and all blocks within
   `max(2.5 km, start view distance)` of the start target are in **and** (by day) the shaders of a frame's passes are
   compiled; then the view is usable and the rest streams under a small bottom progress bar. Trees, rooftops and
   cars stream on their own around the view meanwhile (their `update` runs every 100 ms while loading, nothing drawn).
4. **Defer what the first view doesn't need:** shores and the woods' far carpet load after the view is up; the
   night warm-up runs in the background (section 6).
5. **Meshopt decoding in workers:** `MeshoptDecoder.useWorkers(min(4, max(1, hardwareConcurrency >> 1)))`.
6. `cityReflection.markStale()` once everything is in (capture again with the whole city).

Not addressed (next candidates): `shoreField` (~0.6 s single task). three.js from the CDN (3.6–5 s): preloaded with
`modulepreload` since New York's M9, vendored as an option since London's M9 (section 10).

## 6. Shaders without stalls

**Why:** a node material is built (TSL → WGSL/GLSL) and its pipeline compiled the first time a *pass* draws it: 30–90
ms of script per material and pass, then the driver's compiler (the facade shader alone keeps it busy for ~1 s), for
a dozen materials in each of five passes (shadow, probe, mirror, AO pre-pass, scene). Every new pass × material ×
light/fog combination stalls a frame. Profile of a first switch to night: 40 s total in `_renderObjectDirect`, top
self times in three's node `build`/`analyze`/`getChildren` and WebGL `getUniformBlockIndex`/`getUniformLocation`.

### The mechanism (`main.js`, three 0.186.1 internals)
Override `renderer._renderObjectDirect` with a preparing mode:

```js
const drawObject = renderer._renderObjectDirect;
renderer._renderObjectDirect = function (object, material, scene, camera, lightsNode, group, clippingContext, passId) {
  if (prep.mode === null) return drawObject.apply(this, arguments);
  const ro = this._objects.get(object, material, scene, camera, lightsNode, this._currentRenderContext, clippingContext, passId);
  if (this._pipelines.get(ro).pipeline === undefined) {
    const built = this._nodes.get(ro).nodeBuilderState !== undefined || this._nodes.nodeBuilderCache.has(ro.initialCacheKey);
    if (!built) { const now = performance.now(); prep.deadline ||= now + prep.budget; if (now > prep.deadline) { prep.deferred = true; return; } }
    ro.drawRange = object.geometry.drawRange; ro.group = group;
    this._nodes.getForRender(ro);
    const pre = this._isPreCompiling; this._isPreCompiling = !prep.shadows;       // nested passes (shadow maps) only if asked
    this._nodes.updateBefore(ro); this._geometries.updateForRender(ro); this._nodes.updateForRender(ro); this._bindings.updateForRender(ro);
    this._isPreCompiling = pre;
    this._pipelines.getForRender(ro, prep.promises);                               // async: createRenderPipelineAsync / KHR_parallel_shader_compile
    this._isPreCompiling = true; this._nodes.updateAfter(ro); this._isPreCompiling = pre;
  } else if (prep.mode === 'dry') { /* run nested passes (a pipeline's scene pass) */ }
  if (prep.mode === 'lazy' && this._pipelines.isReady(ro)) drawObject.apply(this, arguments);
};
```

- **`compileOnly(draw, budget)`** ('dry'): runs `draw()` with the backend's `beginRender`, `finishRender` and `clear`
  stubbed — nothing drawn, no target touched — so each object gets its node material built *for the pass it is in*
  (same render target, MRT, context and lights as a real frame, hence the same cache keys) and its pipeline created
  asynchronously. Stops building after `budget` ms (`complete: false` → run again next frame). Returns
  `{ complete, ready: Promise.all(promises), pending }`.
- **`lazily(draw)`** ('lazy'): a real frame that draws what is ready and prepares the rest (≤ **30 ms** of building
  per frame); if incomplete or pending, marks `frameGaps` and `invalidate({ redraw: true })` when ready (plus
  `{shadows: true}`: the shadow map may lack them too). Late arrivals (shores, carpet, first trees/cars) appear a
  frame later instead of freezing the view. The probe capture is made again if it was incomplete.
- **Startup (by day):** before showing the view, loop `compileOnly(framePasses, 200 ms, { shadows: true })` once per
  animation frame until complete (≤ 60 rounds), then await all pipeline promises. `framePasses` = probe `prepare()`
  (into a spare target), water mirror, settled pipeline, plain render (and the glow pipelines at night).
- **Starting after dark (`?time=21`) compiles ahead too** (since Paris M9 round 4; `?nightcompile=0`: lazily, as
  before). It used to keep rebuilding the same shaders and never finish: the shared render context of
  tsl-and-three-pitfalls 39 (the night's passes run the occlusion and the still glow pipelines one after the other).
  Since that fix it completes; drawn lazily instead, the first frame came 3-5 s sooner but was nearly empty (6 draws at
  the overview, ~390 at 9.6 s, gaps until ~20 s), i.e. "usable" wasn't. Ahead, the first frame is complete: under
  80 Mbit/s + 30 ms it comes when a day start's does (the downloads set the time), not later.
- WebGL cost that remains: `_completeCompile` up to ~250 ms when a background compile finishes (most of the
  ~340 ms worst stall). WebGPU has no equivalent step.

### Keeping day *and* night shaders alive (background warm-up)
three keeps one render object per mesh × material × pass, **rebuilds it when the light set or the haze node it was
built for changes** (the render object's dynamic cache key includes the scene's environment/fog/lights key), and
**drops a built shader as soon as no object uses it**. So the first dusk stalled for seconds, and every day↔night
switch threw away the shaders of materials *without* a lit copy (they only saw the fog/light change) and rebuilt them.
Measured without warm-up: every switch froze **16–17 s** (WebGL, Iris Xe).

Fix: **stand-ins that hold the shaders** — for every kind of mesh in view, a hidden mesh sharing its geometry and
material, kept forever, through which every pass is compiled with both light states:
- kind key (what a shader depends on):
  ```js
  const shaderKind = (o) => [o.material.id, o.receiveShadow, o.castShadow, o.renderOrder, !!o.isInstancedMesh, !!o.instanceColor,
    o.geometry.index?.array.constructor.name, ...Object.entries(o.geometry.attributes)
      .map(([k, a]) => `${k}${a.itemSize}${a.array.constructor.name}${a.normalized}${!!a.isInstancedBufferAttribute}`)].join();
  ```
- stand-in: `o.isInstancedMesh ? new InstancedMesh(o.geometry, o.material, 1) : new Mesh(o.geometry, o.material)`,
  same shadow flags/renderOrder/`noReflect`, `frustumCulled = false`. **Instanced like the model** — plain stand-ins
  never held the instanced rooftops' and impostors' shaders, which were rebuilt at every switch (5–6 flickers per
  switch on the Mac).
- steps, each run as `compileOnly(passes, 40 ms)` with the rest of the scene hidden and only the stand-ins visible:
  `['day', framePasses]`, `['sun', env PMREM into a throwaway target]`, then for `sun` and `moon`: probe, mirror,
  settled glow pipeline, still glow, moving glow, plain render — with the lit copies and night fog on.
- scheduling: only **idle** (not moving, ≥ 500 ms since input, ≥ 100 ms since the last step, tab visible; after dark
  only once a frame has left nothing out, so the view's own shaders come first), no frame drawn in that tick; each
  step sets its own light (lit copies, fog, sun or moon, glow on or off) and restores the view's after (until Paris M9
  round 4 it ran by day only, and after a night start nothing prepared the day: the first Day waited 2.8-4.9 s); ≤ 60 rounds per step. Starts as soon as the view is up (not after full load).
  On the slow test GPU it finished between ~25 s and ~2½ min after loading depending on the build, the backend and
  how much streamed in (14 steps, 1–17 rounds each); much faster on the user's Mac. Until then a switch is covered
  (below).
- **Rescan every 5 s** while idle by day for kinds that arrived since (farther rooftops, trees, shores, carpet) and
  warm those too — kinds streamed after the first warm-up had none.
- Result after warm-up: first Dusk, first Night and every later switch build **zero** shaders.

### Covering a change of light (freeze/cover canvas)
If the light changes before the warm-up got that far (a phone may take minutes), lazy frames would bring the new
light in piece by piece. Rule: **from a change of light until the first complete settled frame, a frame that left
something out is never shown bare.**
- On the change: draw the view once more in the old light, copy the canvas into `<canvas id="freeze">`
  (`drawImage(renderer.domElement, 0, 0)`) laid over the renderer; `hold = now`.
- After each frame while held (`presented()`): if nothing was left out → uncover, keep a copy of this frame, and if
  settled end the hold; else keep the cover up (with "Preparing the night lights…" after **400 ms**). Give up after
  **30 s**. Invalidate the copy on resize.
- Iterations that failed, in order: freezing until a *settled* frame showed the note on every switch (the settled
  frame comes 250 ms after stillness and is the heaviest); lifting on touch or after the first complete frame let
  incomplete settled frames through on a phone; covering *every* incomplete frame at night also covered late
  streaming cars/rooftops, so moving water and cars jumped back and forth. Final: only from the change of light to
  its first complete settled frame.
- **Redraws for shaders that became ready stay at settled quality** (`invalidate({ redraw: true })`): counting them
  as view changes dropped the view to a moving frame and back several times per switch (traces also showed the SSAO
  pass's materials rebuilt during those flips), which the user saw as repeated glitches.

## 7. Pitfalls (chronological, each cost a round of user feedback)

1. Rendering continuously while idle → hot laptop. Always on demand.
2. Throttled shadows that only update on big moves looked unnatural in motion → 100 ms refresh while moving.
3. Water in view nearly everywhere kept a 24 fps loop running forever → 12 fps after 30 s, stop after 180 s; hover
   isn't input; ≥ 4 % of the view.
4. SSAO at distance → horizontal bands → fade 3–6 km (log depth converted), skip > 6 km.
5. Night warm-up compiled at load (≈2.4 → 5 s with moonlight) → the "freeze after downloading"; moved to the
   background on stand-ins.
6. Compiling ahead after dark kept rebuilding the same shaders → only compile ahead by day; lazy at night.
7. Fog/light changes invalidate render objects, and unused shaders are dropped → stand-ins that keep day and night
   variants alive.
8. Each switch rebuilt the instanced materials → stand-ins instanced like their models.
9. Kinds arriving after the warm-up had no night shaders → rescan every 5 s.
10. Redraw requests treated as view changes → moving/settled flicker → `redraw` flag.
11. Shadow map drawn inside the probe pass (trees hidden) → missing tree/rooftop shadows after a switch →
    `afterShadows`.
12. Changing a pipeline's output node recompiles its effects (bloom 1.2 s) → prebuilt pipelines, switch between.
13. One-connection-per-request dev server made request count, not bytes, the loading bottleneck → gzipped blocks.
14. A test agent's long performance trace crashed the shared browser; a sleeping display throttled Chrome to
    1 fps and skewed timings (`testing-and-tooling.md`).

## 8. New York (a slow integrated GPU at 2×): what M9 taught

Measured on an Intel Iris Xe at 3200 × 2000, where a settled Midtown frame costs 375 ms of GPU
(New York's M9 metrics). What a fast Mac never showed:

- **Frames in flight.** The loop drew on every animation frame; on a GPU slower than the display, moving
  frames queued 5–7 deep and the picture trailed a drag by 0.7 s. `logFrame` now counts frames until
  `gpuDone()` (WebGPU `onSubmittedWorkDone`, a fence on WebGL 2) and the loop draws no more while
  `MAX_IN_FLIGHT` (2) are in flight: 0.27 s at 7.4 fps. One in flight was 0.16 s but 6.2 fps (the GPU waits for
  each frame's encoding).
- **Pace the animation by the GPU, not the clock.** A 24 fps cap never engaged where a frame takes 270 ms, and
  kept the GPU at 100 % for three minutes after every touch. Each animating frame now waits for the GPU and
  rests as long as it took (half the GPU), and where frames take over 100 ms it stops after 20 s.
- **A change of light is one settled frame** (`invalidate({ redraw: true })` from `setSun` on a jump), and
  things arriving (tiles, trees, cars) redraw the view as it is, merged every 300 ms: through the moving path
  each showed a soft frame first and a sharp one 250 ms later.
- **Measure like for like, in a fresh browser.** Frame times drifted 2–5× over successive loads in one Chrome
  (its GPU process grew to 2.9 GB). Serve the previous milestone's viewer from a copy (`git archive`) on the
  same data and alternate runs; time the settled frame directly (redraws, to GPU done), not fps.
- **Where a load goes:** `performance.mark`s (modules, gpu, ground in, near in, compiled, first frame, all in).
  In New York the first requests to the CDN took 2.3–3.9 s from the office (TLS 1.8 s); three.js's imports
  and the city's first files are preloaded in `index.html` so nothing waits for its parent. At 4× CPU the
  shader compile after the near blocks (9–11 s) dominates: compiling while the data downloads is the next step.
- **Stale layers float.** Rooftop items store their building's base; rebuilding the terrain without
  06c_rooftops hung water tanks in the sky over every district. Run `city3d stale` after any single stage.

## 9. Paris (a dense centre, many materials): what M9 taught

Measured on the same Iris Xe at 1600 × 1000, dpr 2, WebGPU, 80 Mbit/s and 30 ms.

- **Find out what the compile wait is before attacking it.** Paris's "compile" took 5–7 s of the 15 s. A log of
  every node build (`?buildlog=1`, `__viewer.buildLog`) showed only 1.9 s of it was three building node
  materials; the rest was the GPU process compiling ~90 pipelines one after another, during which
  `requestAnimationFrame` (and so the next `compileOnly` round) waited ~0.8 s per round. Async pipeline creation
  is async for the page, not for the GPU process: **any frame submitted after a batch of pipelines waits for
  them.** So what helps is fewer pipelines before the first frame, not a bigger build budget.
- **The first frame needs only its own passes.** Leaving glass's city probe and the moving frames' plain render
  out of the startup compile (`loading.passesLater`) took ~20 of ~95 pipelines off the critical path; they are
  compiled once the first frame is on screen (a moving frame goes through the settled pipeline until then, glass
  reflects the sky alone). Start that work *after* the first frame is on screen: started when the view showed,
  its compiles delayed the first frame by 1.2 s. Make that first frame the settled one, not a moving one followed
  250 ms later by the settled one.
- **Deferring trees, rooftops and cars cost more than it gained.** Usable came 1–2 s sooner, but their shaders,
  compiled lazily ≤ 30 ms a frame with one frame a second while the GPU process compiled, kept the view popping
  in for 20 s more (frames with gaps until > 30 s, against ~24 s with them in the startup compile). Off for
  Paris; kept as `loading.deferLayers` for a city with cheap layers.
- **Block size is a loading lever.** The Cité sits on the corner of four 4 km blocks: 37 MB (40.7 MB with the
  markings) waited for. 2 km blocks (`[blocks] size = 2000`) and waiting only for those the start camera sees
  (`loading.frustumNear`) cut the blocks before the first frame to 19.7 MB and everything done by "near in" from
  57 to 35 MB; near in 7.7–8.2 → 6.0–6.3 s.
- **Draw calls: merge the flat layers per block.** Roads, bridges and markings were 542 of the overview's ~870
  draws at a few thousand triangles each. Merged per block in the viewer (`tiles.merge`; float positions in
  world metres, the other attributes copied as stored — read an interleaved attribute's raw values, not
  `getComponent`, which rescales normalized ones): 866 → 465 draws, settled GPU 375 → 371 ms. The frame is
  fill-bound, so draws were CPU, not GPU, time. Buildings stay per tile (the rooftops' parapets are made from
  each tile's mesh). A tile emptied by the merge must still be added: the rooftops waited for its group and
  asked for a redraw every 400 ms forever.
- **The "leak" was the back-forward cache.** Each load left ~1.9 GB of `free`'s "shared" memory (i915 buffers of
  the GPU process) after navigating to about:blank; destroying the device in the page returned 2.5 GB at once.
  Most likely the old page sat in the back-forward cache with its device (a `pagehide` handler that skipped
  `persisted` pages released nothing). Now `pagehide` always destroys the device (WebGL: loses the context) and a
  page restored from that cache reloads: of a load's 1.3 GB, 1.1 GB comes back within 6 s of about:blank.
- **Check the frame clock before blaming the loop.** M9's eval found moving frames every 0.6-1 s while each took
  100-160 ms of GPU and the main thread was idle, and suspected the loop's pacing. An empty WebGPU canvas on its own
  page got `requestAnimationFrame` exactly every 1,000 ms in the same Chrome: the box's monitor was asleep (DPMS,
  `xset q`), and X then paces frames at 1 Hz. With `--disable-gpu-vsync --disable-frame-rate-limit` the viewer's own
  pacing (≤ 2 frames on the GPU) gave 8-22 fps (Cité orbit: a frame every 103 ms). A 1,000 ms (or 500-600 ms
  "invalidate to done") rhythm is a clock, not work. With two frames in flight the logged "frame start to GPU
  done" is ~2x the GPU time per frame; report the interval between frames too.
- **A pass prepared by day only leaves night frames with gaps.** After a night start the moving frames' glow pass
  was built lazily (≤ 30 ms a frame), so moving frames drew 0-16 draws for a while (at 1 fps, the whole orbit: a
  median of 14 against 139 by day). Whenever a light change makes a pass the frames need and nothing has prepared
  it, draw through a pass that is ready (the settled pipeline at the moving resolution) and prepare the other a
  little at a time in the background (`prepareMovingGlow`), as `loading.passesLater` does by day. Check the frame
  log's `gaps` (and `?buildlog=1`'s `left`) whenever draws drop between day and night.
- **Freeing tile arrays has a consumer.** Since New York's M9 the tile arrays are dropped once on the GPU; the
  rooftops made each tile's parapets from those arrays when the view came within 1.6 km, so tiles away from the
  start view had none. Parapets are now made just before the arrays go, ≤ 8 ms a tick, and the arrays are also
  freed on a timer (frames alone left ~700 MB in the heap while the view was idle).
- **Re-measure everything taken under the 1 Hz clock.** Paris M9 round 2 with vsync off: the Cité's first frame 13.0 ->
  8.7 s, the overview's 14.6 -> 12.6 s, WebGL 2's 18.8 -> 11.1 s, a change of light 1.3-1.9 s -> 0.15-0.45 s, with no
  code change for any of them: the startup compile and the loading loop run one round per animation frame, so a
  slowed frame clock slows the load too. Nothing measured on a sleeping display is a property of the viewer.
- **Gate animation on what an animating frame costs, not on the settled frame.** The settled frame carries occlusion's
  passes and MSAA; an animating frame reuses the occlusion: at the Opéra 93 ms settled against 56 ms animating. Paris's
  settled frames were all over the old 150 ms limit, so no water or traffic ever moved. `animation.gate = 'frame'` draws
  them, stops at a view where two in a row take > 70 ms (under ~10 fps), and paces the rest at two thirds of the GPU
  (a third after 30 s, so the halving shows even where the GPU, not the 24 fps cap, sets the rate: with "rest as long as
  the frame took" the cap's halving to 12 fps never engaged at 8 fps). Default stays `'settled'` for cities tuned on it.
- **Wait for a calm warm-up before timing a change of light.** `warmLeft() == 0` is also true for a moment between two
  batches (a rescan for kinds that streamed in comes every 5 s): a switch then still built the new kinds' night shaders
  (1.85 s, 4 covered frames), against 0.42-0.44 s once nothing new turned up for 7 s.
- **Find a long task by timing three's internals in the page, then log the cache key's parts.** A 15 s task after a
  night start at the overview: wrapping the renderer's and its managers' methods (`_objects`, `_nodes`, `_bindings`,
  `_pipelines`, `backend`, the device) found `RenderObjects.get` re-creating ~400 render objects; logging each
  replaced render object's key parts showed only `renderer.contextNode` changed, and a CPU profile
  of the task showed 13 s of it in dispose building never-built objects. Cause: the occlusion pipeline's scene pass and
  the glow's still pass shared one render context (three keys contexts by format, samples and MRT, not by target) while
  only the first has a `contextNode`; after dark at a far view the moving frames went through one and the settled
  ones through the other (tsl-and-three-pitfalls 39, 40). Fixed with an MRT on the scene pass and a dispose guard:
  longest task after usable at the overview 10.8-15.8 s -> 0.28-0.32 s (with the per-frame budget below), the first
  Night after a Day 14.0 s -> 162 ms on screen (longest task 87 ms). A budget around
  `_objects.get` alone would not have done it: the re-made objects would have been rebuilt every time the two passes
  alternated. When a stall is "three rebuilding", find which key part changes before budgeting it.
- **One build budget per frame, not per pass.** Each lazily drawn pass (glass's probe, the water's mirror, the view)
  had its own 30 ms, and each may overrun it by one material (a facade ~100 ms, the backdrop 145 ms), so a night
  start's first frames ran 360-450 ms tasks. One deadline for all the frame's lazy passes and the moving glow's
  preparation (`frameBuildDeadline`; the moving glow prepared after the view) keeps them at 280-320 ms. What a night start still costs is
  time, not stalls: the view fills in over 8-14 s, ≤ 30 ms of building per redraw and a redraw every 300 ms.
- **A frame is complete only if nothing in it is still compiling.** The lazy loop counted a frame as complete when
  it built nothing new and got no new pipeline promise; objects whose pipelines were asked for in an earlier frame
  and were still compiling were skipped by three without a word (tsl-and-three-pitfalls 41), so the change-of-light
  cover went at a frame with a few dozen draws and 9-10 frames with gaps followed (Paris Cité and New York Midtown
  after a night start). Counting those as left out took the gapped frames after the cover to 0 in every switch
  measured; no "N complete frames in a row" rule was needed.
- **Warm the light that is not on, whichever it is.** The background warm-up ran by day only (round 2's attempt at
  night stalled on the shared render context, since fixed), so after a night start the first Day built everything
  behind the cover: 3.1 s at the overview, up to 4.9 s at the Cité. Running the same steps by night, each in its own
  light (and the day step drawing the stand-ins into the sun's shadow map, which nothing draws after dark), gave
  0.40-0.42 s at the overview, 0.27-0.33 s after an orbit at the Cité and 1.6-1.8 s settled there; the warm-up's
  stand-ins are keyed by the *day* material (`night.dayMaterial`), or a scan after the switch takes the lit copies for
  new kinds. What it doesn't reach: the day shadow map's casters themselves (tsl-and-three-pitfalls 42).

## 10. London (traffic, the CDN): what M9 taught

Measured on the same Iris Xe at 1600 x 1000, dpr 2, WebGPU, vsync off, 80 Mbit/s + 30 ms.

- **Vendor three.js where the CDN is a risk** (`city.json "three": "local"`, `engine/vendor/three@0.186.1/`, the npm
  package's files, MIT). The import map can't be switched after the fact, so `index.html` writes it (and the
  modulepreloads, the engine's own modules too) from a small script once city.json is in; that wait cost nothing
  measurable. Modules 2.6-3.2 s -> 1.05-1.09 s, usable -1.6 to -2.1 s (City 8.8 -> 6.7-7.2 s, overview 10.8 -> 8.7-8.9 s),
  and the evenings when jsDelivr took 8-18 s are gone. Import map values must start with `./`, `../`, `/` or a scheme:
  a bare `engine/vendor/...` is ignored with only a console warning, and nothing loads. A fallback CDN on error is not
  possible with one import map (a specifier resolved once stays resolved); it would need a reload with `?three=`.
- **Traffic over a picture of the city** (`animation.overlay` then, part of `animation.full` now). Where only cars and water move, the city is drawn once
  (cars and water left out) into a render target with the canvas's format, type, samples and depth/stencil flags
  (three r186 keys render contexts by exactly those, not by the target: so the same render objects and pipelines,
  nothing compiled), and each animating frame is a full-screen quad writing that colour and depth (`depthNode` from a
  `.load()` of the multisampled depth texture's first sample, `depthTest = false`), then the cars and the water over
  it, drawn with the camera on a layer only they, the quad and the lights are on (the same light set, or the cars'
  render objects would be rebuilt). The Strand: 59 ms (M8) / 37 ms cheap frames at 1.25x -> **11 ms at 2x**, 13 draws,
  24 fps. Two traps: a picture made at another resolution than the frame (the first one, at the moving resolution)
  reads its depth at the wrong pixels (cars through walls, the far ones gone): check the size every frame; and
  the load's pixel rows run the same way as the fragment's `screenCoordinate` (flipping them put the skyline upside
  down in the street). Hide the quad (`visible = false`) except while drawing it, or a scan of the scene for shaders
  to warm picks it up. A third trap, in a city with a sea (Hong Kong, 6 Oct: "thin bright white lines along almost
  every water edge", at 1x and 2x, only while waves or traffic moved: the stats line says "waves + traffic", ~11 draws): the sea plane is depthless, so a
  picture made without the water has the cleared sky under it, and a pixel on the water's edge gets the resolved mix
  of its samples (quay and sky) as colour but its first sample's depth (the quay's), so the water drawn over it fails
  there: a 1-px sky-coloured line along every quay, seawall, pontoon and roof edge over the water. City.json
  `animation.overlayWater` (opt-in) keeps the water in the picture and draws it again over it each frame (its surface
  doesn't move, so it meets itself at the same depth), with the shallows' veils (`userData.overWater`). River cities
  (water lying on the ground) never showed it. The same trap for anything that blends without writing depth in
  front of the water: the Eiffel Tower's lattice panels vanished against the Seine in every animating frame (Paris,
  7 Oct), since the picture kept the river bed's depth behind them and the frame's water covered them. `overlayWater`
  doesn't help (the water meets itself at the same depth and still covers what blended over it); city.json
  `animation.overlayLattice` (opt-in) leaves the lattices out of the picture and draws them over it and the water
  each frame.
- **Don't let the warm-up stop the animation.** The background warm-up's pipeline builds delay the GPU's next frames
  (72-288 ms spikes at the Strand); two such frames in a row stopped the traffic for good until the view moved (M8:
  "stopped at once", "stopped after 9 frames"). Cheap frames while the warm-up runs (or within 1.5 s of a step) no
  longer count towards the stop (now any animating frame: see below; the cheap frames themselves are gone, see
  "Removed" at the end of section 11).
- **Re-measure the claim before optimising it.** The brief's "59 ms, 5 fps" came from a run during the warm-up; after
  it the same cheap frames took 37 ms (~18 fps). The overview's "197 ms settled" (M8, a call-to-GPU-done measurement)
  was 116-119 ms in the frame log, under Paris's 148-154: nothing to fix there.

### London M9 round 2 (the critic's 6/10)

- **WebGL 2: ask the driver for one program at a time in the background.** The warm-up's rounds (40 ms of node
  building each) asked for a dozen programs at once; they queue in the GPU process, and the next call that has to
  wait for the driver (a link status, a uniform location) stalls the page: 1,204 ms (M9) and 3,808 ms (round 2, before
  the fix) during the City's warm-up, under 80 Mbit/s + 30 ms, in 1 load of 2 each time. Now each warm-up round on WebGL
  asks for at most one new pipeline (`WARM_NEW`, `prep.maxNew`) and the next waits until it is compiled
  (`warmPending`): 230-261 ms longest task once usable in the next loads, and the warm-up still done at ~45 s. WebGPU
  builds its pipelines asynchronously without such a wait: unlimited there. The programs' completions are also polled
  from tasks of their own instead of three's per-program rAF callbacks (none took over 20 ms; keep it as a guard).
- **An overlay's underlay must be the settled frame's own pass.** Made by a plain render under a frame drawn with
  occlusion, the picture behind the moving cars was 9-10 % brighter (mean |diff| 7.0-7.2 of 255; the Thames lighter, no
  occlusion at the buildings' feet), so the view popped at every start and stop of the traffic. Now the picture is
  the settled pipeline's scene pass drawn again without the cars and the water (its occlusion context, the AO texture
  as the settled frame left it), and the overlay frame draws it, the cars and the water through a pass of the same
  kind and the pipeline's last step (AO multiply, tone mapping): mean |diff| 1.6-2.3 over the frame, 0.3 outside what
  moved, brightness within 0-1.6 %. Three traps on the way: the pipeline's output node samples the AO texture, so
  rendering it runs the AO pre-pass and SSAO again every frame (78-93 ms overlay frames, the traffic stopped) unless
  they are frozen (`freezeAO`); a second pass node has render objects of its own, built at once a 1.7 s task: prepare
  them a little per frame (`compileOnly(..., WARM_MS)`); and the picture's own render must be lazy (the scene pass meets
  trees and rooftops streamed in since the last settled frame): a picture that left something out is not used.
- **Measure "picture pops" with a pixel diff**, not by eye: a settled vs animating
  screenshot, waves off, the moving cars masked by a 24-level threshold).
- **A vendored library needs its files in git, not only on disk.** The repository's `.gitignore` has `libs/`, so
  `vendor/three@0.186.1/examples/jsm/libs/meshopt_decoder.module.js` never got committed: every checkout of a
  `"three": "local"` city stuck on its loading screen (the critic's "partial vendor folder"). A `.gitignore` in
  `vendor/` re-includes it. Load a fresh checkout before calling a vendored copy done.
- **Module loading can fail: fall back once, then say so.** `index.html` catches the dynamic import's rejection: no
  `modules` mark yet means the module graph failed, so the page reloads once from the other source
  (`?three=cdn|local&threefallback=1`); the CDN also gets 25 s before that. If both fail the loading box says so; an
  error after the modules were in is shown as the viewer's error. Tested with CDP `Network.setBlockedURLs`.
- **Version, don't Date.now(), the engine modules where the page is published.** A fresh query string per load made
  returning visitors fetch all 16 engine modules again; it is now `ENGINE_VERSION` (+ city.json `version`), and
  `Date.now()` only on localhost, private addresses, pages on their own port or `?dev`.
- **The slow-frame gate's warm-up exemption is for every city.** Paris's Pont des Arts (full animating frames, no cheap
  ones) stopped its animation at once in one run of two: its first animating frame took 101.6 ms (54 normally) while a
  rescan's new kinds (streamed in after the view moved) were being compiled, and only cheap frames were exempt. Slow
  frames while the warm-up works (a step in the last 1.5 s, steps left, or its pipelines compiling) now never stop
  the animation.
- **Cap the animation on the time since the last frame.** A fixed beat with 4 ms of slack let frames come 38 ms apart
  (25 fps read against a 24 cap). Now >= 1000/24 ms since the last animating frame (on a 60 Hz display: 20 fps).
- **What a critic calls a car's shadow may be the road.** The "dark translucent rectangles and wedges behind the cars"
  at the Strand stayed with the cars hidden: the markings shader's repaving patches (whole lanes 15-60 m long at
  x 0.72 / x 1.22, wedge-shaped where a strip's lanes widen). Hide layer by layer before changing the suspect;
  `markings.repaving` now sets their share and tone (London subtler). The rectangles right behind each car were the
  cars' planar shadows (gone with their material switched off), geometrically right (the sun behind the camera at
  ~17 degrees throws each a car's length up the street, flat on the road, one layer) but evenly dark, so they read as
  boxes: `cars.shadowFade` (London 0.5) lightens each towards its far end, a widening penumbra.

## 11. Berlin (a near-only detail branch, the warm-up's changes of light): what M9 taught

- **A branch cut by distance must hold for every camera that draws the tile.** `facade.nearDetail` (since removed,
  see below) drew far tiles
  with a copy of the facade material without the city's detail branch, cut from the view's camera only; the glass
  probe (six 256-px cube faces at the orbit target) and the water's mirror draw near tiles the view sees from 13 km.
  The cut now ANDs the view, the box mirrored in the mirror plane (the mirror's camera sees the box as the view sees
  its image, at half the resolution or less) and each cube face that sees the box (least depth along the face's axis;
  the pitch factor 1 on the side faces, tan t up or down). Cost at the overview: 7 tiles of 69 back to full, within
  noise (212 against 213 ms).
- **Two programs for the same math are not bit-identical.** The full facade program with the branch switched off by
  a uniform and the lean copy differ by up to 6 levels over 163k pixels at a low oblique view (the shared code compiled
  twice); where every wall is averaged (the overview) they agree to the bit. So an exactness test of a material swap
  can only ask for 0 where the walls are fully filtered; elsewhere compare against that "branch off" program, not 0.
- **Like for like across milestones**: the old viewer (`git archive <commit> engine/viewer city.json`) served next to
  the new one from one server over the same data, one load of each per Chrome session, the order swapped between
  sessions (Berlin). M9 against M8: equal at Mitte and the street, -4 % at the overview; the
  whole branch gone would save 10 % at Mitte and 8 % in the street (its size, not its work).
- **A change of light during the background warm-up waits under the cover for 5-10 s** (Berlin, Iris Xe): the new
  light's shaders are built at BUILD_MS a frame while the GPU process compiles them one after another; after the
  warm-up the same click takes 0.3-0.6 s. `loading.holdBuildMs` (off by default) lets the unseen held frames build
  more: 100 ms took Mitte's Night from ~10 to 7.8 s and Day from ~9.8 to 4.9 s (one load) for a 319 ms longest task.
- **Measure interaction during the warm-up**, not only after it (orbit, Night, Day, zoom, the time slider while the warm-up runs): orbits and zooms were
  fine (36-60 frames in 4-5 s, tasks under 240 ms), the light changes were not.

### Removed (October 2026): cheap frames, the near-only facade, moving-frame detail

Three fallbacks went from the viewer once no city set them; the lessons above stay.
- **`animation.cheap`** (London M6): where two full animating frames took over `slowMs`, the animation went on at the
  moving resolution without occlusion or multisampling. It kept the traffic running on the Iris Xe, but the city
  blurred every time the cars moved (Berlin, on a Mac). `animation.full` replaced it: always full resolution, the
  overlay (the settled frame's picture with the cars and water over it) by day on WebGPU, else full frames, stopped
  where two take over `slowMs`. `animation.overlay` went with it (its picture is part of `animation.full`).
- **`facade.nearDetail`** (Berlin M9): far tiles drawn with a copy of the facade material without the wall-detail
  branch. ~10 ms saved, at the overview only; on WebGL 2 the second facade program cost more than it saved (slower
  load and first Night), and the exact cut needed the probe's and the mirror's cameras too. Not worth the code.
- **`facade.movingDetail`** (Berlin): the wall detail, curtains, awnings and railings left out of moving frames, the
  window grid faded at half the distance. Berlin turned it off with nearDetail (the same facades near and far, moving
  and still, as every other city).

## 12. The first minute on every backend (the warm-up fix, all cities): what it taught

Measured at Berlin (Mitte, the overview) on the Iris Xe, 1600 x 1000 at dpr 2, 80 Mbit/s + 30 ms, vsync off,
an interaction script over CDP with the viewer's `?warmlog=1`.

- **Find out whether the driver compiles in the background before limiting what you ask of it.** London M9's
  "one program per warm-up round" (`WARM_NEW`) counted the pipeline *promises* a round made. Chrome's ANGLE on
  Vulkan (this box's Chrome with the WebGPU flags, `?webgl=1`) has no `KHR_parallel_shader_compile`; three then
  compiles and links each program at once and makes no promise, so the limit never applied: 569 programs linked
  synchronously in one overview load (9.3 s of main thread, single links up to 1.2 s), and a frame after a change
  of light linked every program it met. Count links instead (`createRenderPipeline` calls): at most one per
  warm-up round, per held round and per drawn frame on WebGL 2 once the view is up (`LINKS_GL`, `?glLinks=`), and
  none while one is still compiling where the extension exists (`GL_QUEUE`). Check with
  `gl.getExtension('KHR_parallel_shader_compile')` on the test browser; a plain Chrome on Linux (ANGLE on OpenGL)
  differs from the one with the Vulkan flags.
- **On WebGL 2 a synchronous call waits for every frame queued before it.** A link, a canvas or render-target
  resize (the moving <-> settled resolution switch) or a redraw issued while the GPU was still on a 0.5-2 s settled
  frame took the main thread 0.6-1 s and, piled up, lost the GPU process. Such work now waits for `inFlight == 0`
  (`glBusy`, released after 6 s without an answer: Paris's frames during the warm-up took up to 3.4 s, and with 2 s a
  link waited 1.3 s for one) without blocking: the page stays responsive and the GPU does the same work. Count every
  render that reaches the GPU as in flight, also the one-off ones (the cover's frame of the old light: the first held
  round linked a program right after it and waited 0.5 s), and don't make that one-off render while the GPU is busy
  (it waited 1.1 s in the click's task at the Cité): with the held rounds drawing nothing until the new light is
  complete, the canvas itself still shows the old view.
- **A limit on what a frame may build needs a way out.** With "no link while the GPU is busy", a redraw for what a
  frame left out came at once, found the GPU busy, linked nothing, left the same out: settled frames with gaps for
  good (a run timed out). Redraws on WebGL 2 now wait for an idle GPU, and a redraw after 250 ms of stillness while
  a change of light is held is a settled one (the moving redraws had kept the view "moving", so the held change
  waited 13-16 s at the overview and Mitte).
- **Don't draw what the cover hides.** Under the change-of-light cover every frame drew the whole view (0.3-0.55 s on
  the GPU) to find it still incomplete, and built 30 ms of the new light's shaders. While the view is still, the held
  change now runs `compileOnly` rounds of the view's passes (~60 ms of building each, the sun's shadow map too when
  the frame will draw it) and draws once a round finds nothing left and its pipelines are ready; WebGPU keeps building
  while its pipelines compile, WebGL 2 waits for each round's programs (one at a time without
  `KHR_parallel_shader_compile`; up to four where the driver compiles in the background: one at a time, the Day after
  the slider waited 7 s for 106 programs of 10-50 ms each in a plain Chrome).
- **Throttle what an input event renders.** `setSun` made the sky's PMREM on every call; the time slider calls it
  ~60 times a second, each a cube render and its blur levels queued ahead of any frame (the 2.3-2.9 s tasks of the
  slider step on WebGL 2, and the 1-2 fps drag on WebGPU). It is now made once before the next frame drawn.
- **Order the warm-up by what a visitor clicks**: the day's remaining passes, the sky map, then the *settled* passes
  of the night (moonlight) and of dusk, then their moving passes; paused while the view moves, while a change of
  light is held, and for 1 s after any input.
- **Say when the GPU is gone.** A lost context or device (other than the page releasing it on `pagehide`) shows
  "The graphics card stopped responding." with a Reload button; a measurement script should fail a run that lost it or whose
  settled frames drew nothing (a dead WebGL context times every frame at ~5 ms with 0 draws).
- **Left after the fix** (WebGL 2): a change of light in the first minute still takes seconds (Night 3.6-7.6 s at
  Berlin, Paris and London; WebGPU 3.2-5.1 s), only without the stalls; in Chrome's ANGLE on OpenGL a Day clicked right
  after the slider took 14-18 s, its held rounds "complete" while each real frame then found one or two more
  pipelines (a pass the dry rounds don't run as the frame does: not yet found); a WebGL 2 frame task right after a
  multi-second GPU frame (Paris's orbit during the warm-up, 1.6 s once) can still wait for it.

## 13. The warm-up made fast again on WebGL 2 (all cities): what it taught

The warm-up fix (section 12) paced the first minute to one program at a time on WebGL 2, and New York's background warm-up
(usable -> `warmLeft() == 0`) went from 11.5 s on the 30 Sep viewer to 22.8 s at the Manhattan overview, 20 -> 43 s at
Downtown Brooklyn; Berlin's Mitte took 91 s. Measured on the Iris Xe in Chrome's ANGLE on Vulkan (no
`KHR_parallel_shader_compile`), 1600 x 1000 at dpr 2, vsync off, each load in a fresh Chrome, with an instrumented
page (`linkProgram`, `getProgramParameter`, every node build and long task logged, `?warmlog=1`).

- **Look for the same program linked twice.** A per-program log showed the SSAO's two programs (`SSAO.AO`,
  `SSAO.Blur`) linked again and again: 40-55 % of New York's warm-up links, 200 of Berlin's 426, each using up a
  round's one link. Two causes, both three's: a post-processing node's `setup` (`SSAONode`, `BloomNode`) assigns new
  fragment nodes and `needsUpdate` to its internal quads' materials, and it runs again for every material built that
  samples its output (each scene-pass material in each pass and light), so every warm-up round that built something
  gave the quads a new program cache key; and a render object's cache key includes `renderer.contextNode`'s id, so a
  pass run once a frame for whoever asks first (the pre-pass, the SSAO) got another key when asked from inside the
  scene pass (its occlusion context on the renderer) than from the pipeline's output. Set such nodes up once
  (`setupOnce`) and run them under one context node: no SSAO link left in the warm-up, programs per load 295 -> 182
  (Manhattan), 483 -> 283 (Brooklyn), 583 -> 341 (Mitte).
- **Pace what interaction meets, not what an idle page does.** One link a round and a round every 100 ms made the
  warm-up ~10 programs a second. With no input for 1 s, nothing on the GPU and no change of light held, a WebGL 2
  round without the parallel extension now links up to 8 programs or 20 ms of linking, builds for 60 ms counted from
  the round's start, and comes 40 ms after the last began; frames, held rounds and interaction keep one at a time.
  A link under 3 ms (a program the driver had already) counts against nothing.
- **Don't build and link a big material in one task.** A Berlin facade is ~175 ms of node building and ~60 ms of
  linking: one round doing both was a 240-250 ms task. A material whose build ends past 60 ms of the round is linked
  in the next round, and a round's build budget counts from its start, so a round begun with links builds little:
  the longest task holding a warm-up round at Mitte 250-279 -> 206-212 ms.
- **A uniform-switched branch still costs its node build in every city.** The node builds that doubled since 30 Sep
  were the ground's: the town layer and the backdrop held Paris's block-mass and land-cover paths behind uniforms
  (`calm`, `COVER.on`), ~135 ms of node building each per pass and light in New York, which uses neither (3.3 s of its
  7.5 s of warm-up building). What tiles.json decides for the whole visit (cover maps, mass tiles) is now decided when
  the material is made (`createGroundMaterials(..., { area })`), leaving the other paths out of the graph; what
  arrives during the visit (the cover maps, after the first frame) stays a uniform. Count node builds offline to find
  such things: three's GLSL node builder runs in Node.js with a stub canvas and an import hook for `three/webgpu`,
  and the number of `Node.build` calls is deterministic where timings in a busy browser are not (New York's town
  layer 47,100 -> 12,600 nodes, its backdrop 54,300 -> 17,300; the old viewer's 9,200 and 13,700).

| WebGL 2 (ANGLE Vulkan), 3 loads (30 Sep: 4-5) | usable s | warm-up s | programs | longest task after usable, ms |
|---|---|---|---|---|
| New York, Manhattan overview: 30 Sep / before / after | 5.8 / 7.1 / 6.0 | 11.6 / 22.8 / 10.5 | 266 / 295 / 182 | 120 / 194 / 128 |
| New York, Downtown Brooklyn | 6.6 / 7.9 / 6.9 | 20.4 / 43.3 / 16.1 | 411 / 483 / 283 | 199 / 206 / 124 |
| Berlin, Mitte: before / after (2 loads; 1 with the probe prepared) | 8.8 / 8.4 | 91.2 / 42.8 (39.0) | 583 / 341 | 260 / 307 (216) |
| Paris, overview: before / after | 9.8 / 9.4 | 36.3 / 16.8 | 405 / 237 | 218 / 187 |

WebGPU (1 load each, its pace unchanged: the SSAO, bloom and ground fixes only), warm-up s and longest task ms before ->
after: New York's Manhattan overview 15.0 -> 10.0 s, 204 -> 111 ms; Downtown Brooklyn 19.8 -> 17.8 s, 184 -> 141;
Berlin's Mitte 34.6 -> 32.3 s, 281 -> 229; Paris 18.9 -> 17.0 s, 207 -> 178; London 20.3 -> 18.7 s, 224 -> 182;
Shenzhen's Futian 18.6 -> 15.6 s, 205 -> 137. Shots after the warm-up at a fixed clock (`__viewer.film`) equal the
old ones within a few levels in every city but for the drifting clouds and where traffic placed its cars.
An interaction run on WebGL 2 (orbit, Night, Day, zoom, slider, Day while the warm-up
runs), before -> after: Mitte no GPU lost either way, the load's longest task 1542 -> 304 ms, Night on screen 6.6 ->
5.5 s, Day 3.0 -> 2.6 s, the orbit's longest frame gap 1.4 -> 0.3 s; New York's overview the longest task 376 -> 141
ms, Night 2.8 -> 1.7 s, Day 0.85 -> 0.72 s.

- **Left**: Berlin's warm-up is still ~40 s: 16 s of node building (its facade ~175 ms, the town layer, the land) at
  ~50 % of the main thread, and the animating frames (water, traffic: ~410 ms of GPU each) holding it for ~8 s while
  they draw (`glBusy`).
- **Prepare a capture before its first frame.** With `loading.passesLater` glass's city probe was captured as soon
  as the view showed, and that capture built its own passes, the sun's shadow map drawn inside it among them (another
  call depth: a render context and a ShadowMaterial build of its own, 110-143 ms). At Mitte that landed on top of the
  capture's own work in the second frame on screen: a 305-308 ms task. The passesLater preparation now runs the
  capture's passes without drawing first (`probeReady`); the build is a task of its own (~200 ms) and Mitte's longest
  task after usable is 216 ms.
- **Check a speed-test "worse" in a protocol of its own before chasing it.** The quick speed test flagged WebGPU's
  animating frames at Paris's Avenue de l'Opéra +13-18 % (27.0-27.1 ms against 22.9-23.9). Same-session A/Bs of the
  quick test gave the new viewer 24.7-25.2 ms against 26.6 (SSAO fix reverted) and 24.5 (town layer's uniform branch
  back); loads that only measured the animating frames, 3 x 5 s each after the warm-up, gave the old viewer
  24.6-25.4, the new 22.3-24.5, the ground materials in their old creation order 24.8-25.4 and the town's uniform
  branch 24.0-24.6 (three's opaque sort doesn't use material ids); the final quick test 23.4 (baseline 22.9). Run-to-run
  noise of ~±2 ms, not a regression.

## 14. A change of light during the warm-up on WebGL 2 (Singapore M9 fix round 1): what it taught

Singapore's M9 critic found WebGL 2's first minute stuck behind the cover: Night clicked during the warm-up 7.1 s to
the screen, Day at street level 6.8 s, the time slider dragged 16:00 -> 22:00 nothing new for 10.3 s. Measured with
`?warmlog=1` on the Iris Xe (Chrome's ANGLE on Wayland, `KHR_parallel_shader_compile` present):

- **Count the programs and time the driver before changing the schedule.** Night at the overview asked for 29 new
  programs, Day at Orchard Road 54, the slider's landing light (the moon's, at street level) ~75. The driver linked
  them at ~150-300 ms each, a glass or facade program up to 1.1 s, and in effect one after another: the driver was
  busy 4.7 of Night's 6.4 s. Building (TSL to GLSL) was a few hundred ms of it. No schedule makes 75 programs cheap;
  what a schedule can do is not leave the driver idle and not ask for programs nobody will see.
- **Keep the driver's queue full.** A held round waited until every program of the round before had linked, so one
  1.1 s link left the driver idle behind it. The next round now runs as soon as fewer than 4 are still compiling
  (`?heldfill=0` turns it off). Same programs, same final frame.
- **A dragged slider prepares only where it lands.** Under the cover, the frames drawn while the slider moved linked
  the programs of each light it passed (dusk by the sun, then the moon), one a frame, and drew 0.5-1 s GPU frames
  nobody saw. Now nothing is drawn or prepared under the cover until the slider has rested 250 ms (`?timerest=0`).
- **The first frame of a new light is slow on the GPU too**: 2.0 s (Night, overview) and 2.8 s (moon at Orchard)
  for the first settled frame after the held rounds, against ~0.4-0.7 s once warm: the driver finishing its work at
  first use. It is part of every click-to-screen figure above and no scheduling removes it.
- **Measure old against new in one tree, one session.** Both switches default on and turn off by URL, so `?heldfill=0&
  timerest=0` is the old viewer exactly; pixdiff got `--params` for the same A/B of pictures.

Singapore WebGL 2 `--full` before -> after (one load each, the M9 critic's run against this round's): the longest task
after usable 571 -> 469 ms (the slider's 571 -> 279; the rest is Night's first held frame), Night on screen 7.1 -> 6.6
s, the slider's settled night frame 13.5 -> 11.4 s after the drag, Day again 6.8 -> 6.5 s. In-tree A/B with the
switches off (`?heldfill=0&timerest=0`, one load each, WebGL 2): New York's overview Night 6.5 -> 5.9 s, Shenzhen's
Futian Night 11.8 -> 10.3 s; pixdiff old against new the same (NY and Shenzhen, day and night, WebGPU and WebGL 2;
one Shenzhen WebGPU night shot differs by the known intermittent bloom ball, in the old shot). A load-to-load spread
of ~0.5-1 s on these figures: the gains are real but modest. Two loads in one Chrome profile are not independent: the
second gets the first's compiled programs from the GPU disk cache (New York's Night 6.5 s in a fresh profile, 1.7 s as
the profile's second load); compare old and new each in a fresh profile.

## 15. Tokyo M9: what it taught

Measured in-page (variants of the building material and layers switched off in one load,
A B B A, WebGPU on the Iris Xe at 3200 x 2000 settled).

- **Read a draw count in the frame log, not on the stats line after a change of light.** M8's critic read "dusk draws ~2x
  night" (510 against 274 at Tokyo Tower) from the idle stats line 4 s after setting 17:30. The first settled frame after
  any change of light also captures glass's city probe (`cityReflection.markStale()` in `setSun`; ~240 draws and ~8 M
  triangles in that one frame); the frames after it at 17:30 (sun -5.6 degrees: the moon's light, no shadow pass) drew
  241 / 251 at Ginza / Marunouchi, the night's own counts, and took the night's time. One capture per change of light,
  not waste.
- **A feature already in a branch can still cost by the shader's size.** Tokyo's vertical signboards run in an `If` only
  narrow zakkyo fronts enter, yet the material without them was 15-19 ms faster by day and 32-34 ms at night at Ginza and
  Marunouchi, where few boards are in view; the four Tokyo patterns inside the bays branch 12-16 ms. Building the night
  emission's boards from a second branch of their own (instead of keeping the first one's colour and mask alive to the
  end of the shader) bought nothing (0 to +14 ms): not register lifetime, the program's size. What does pay:
  `night.glowBranch` (Singapore M9) took 12-19 ms off Tokyo's night frames (the Skytree's and Tokyo Tower's lattice glows,
  13 cylinders), pixels the same.
- **Without the buildings Tokyo's day and night frames are equal** (Ginza 125 / 138 ms, Marunouchi 178 / 178): the whole
  night overhead is the facades' night emission (145-191 ms of 282-369), as in Hong Kong.
- **Animation where the overlay exists only** (`animation.webgpuOnly`): the city's `gate: 'frame'` and `full` on WebGPU
  (the overlay: Ginza's traffic 18 fps at 19 ms a frame, 17 draws; Rainbow Bridge's waves and traffic 18.5 fps, 8 draws),
  the defaults on WebGL 2, where `full` without the overlay draws whole frames (~3.5 fps in Singapore's critic run).
- **A Tokyo load leaves little room on a 15 GB machine** (Chrome 3.4-3.7 GB RSS plus 3-4 GB shared GPU memory): each
  facade variant compiled in-page costs a few hundred MB more, and the 1.5 GB floor stopped every WebGL 2 in-page split
  after two variants and both quick speed tests before their last views. Start a session only once "available" is back
  over ~6 GB after another agent's Chrome closes: it returns over a minute or two.

## 16. The M9 fix round's own regressions on WebGL 2 (Singapore M9 critic round 2): what they taught

- **Profile before believing a diagnosis.** The critic read the slider's 1.7 s task after the warm-up as the landing
  light prepared in one synchronous step. A CPU profile and the frame log put it 0.22-0.26 s into the drag, before
  the light changed at ~1.9 s: two moving frames at the drag's start each took the GPU ~2 s, and the page's next
  submission waited for them as a 1.6-1.7 s `(program)` task (native, no JS under it). The landing light was already
  prepared in held rounds (`warmlog`: `held` 1..10, then the frame). The same two ~1.9 s moving frames and a 1.1 s
  task came at the start of Shenzhen's first-minute drag (warm-up running); New York's drags, and Singapore's with its
  animation stopped first (`idle(600)`, the same view and drag in the same load), gave 130-590 ms frames and no long
  task. Not explained yet: it came with and without the animation running and with the warm-up done (the frames'
  cost, not the light's preparation). On WebGL 2 a second moving frame queued behind a slow one is what turns a slow
  GPU frame into a long main-thread task.
- **A shadow map is drawn at most once per animation frame** (three's ShadowNode keeps a frame id per camera). A held
  round that prepares passes with shadows on runs the shadow node; a frame drawn in the same animation frame keeps the
  map as it was. The first frame of a new light then came out complete, so uncovered, without fresh shadows, and the
  towers' shadows popped in 0.3 s later. Draw the frame at the next animation frame (`?heldnext=0`: as before).
- **Two rules that both touch the resolution must not take turns.** The slider's rest rule (settled resolution) ran
  after the moving frames' branch (moving resolution): two canvas resizes a tick for as long as a drag under the cover
  lasted. Check it first.
- **A setting that needs the overlay should say so.** `animation.full` with gate `'frame'` on WebGL 2 (no overlay)
  drew the whole city as each animating frame (~270 ms), and the warm-up's exemption for slow frames kept it going
  while rescans after a jump or a change of light found new kinds (`animState`: `warming` 9 -> 6, `animSlowRun` 0
  through 16 samples). Singapore now sets `animation.webgpuOnly` (Tokyo M9's opt-in): gate and full on WebGPU only.
