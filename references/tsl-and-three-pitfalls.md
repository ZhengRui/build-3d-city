# TSL and three.js pitfalls

Concrete gotchas hit while building the viewer (`engine/viewer/`) for eight cities on three.js **0.186.1**
(`WebGPURenderer`, WebGL 2 fallback, TSL node materials). Each: symptom → cause → fix, with the city where it
showed. Code references are `engine/viewer/*.js`. For TSL basics use the `webgpu-threejs-tsl` skill; this file is
only what bit us.

## Shader graph

**1. `select` between heavy branches → black or garbage pixels.**
TSL compiles a `select(cond, a, b)` whose operands are non-trivial into an `if/else`; a node first built inside one
branch is declared in that branch's scope, so the other branch (or later code) reads it uninitialised. Facades went
black in places. Fix: branchless choice, every node at the top level:
```js
const f01 = (c) => select(c, float(1), float(0));   // select between two constants is fine
const sel = (c, a, b) => mix(b, a, f01(c));
```
`select` between constants or cheap leaves is fine (`pick(style, values)` chains in facade.js).
It is undefined behaviour, so it shows up per driver: New York's impostor trees (trees.js) computed their
shadow-lookup offset through `select(isPalm, h / hc, w / Rc)`; the offset came out huge on WebGPU on every
machine and on WebGL 2 on some, and trees in a tower's shadow stayed lit there, while the same value sized the
card correctly a few nodes earlier. When a shader term is right on one machine and wrong on another, look for a
`select` with non-trivial operands first.

**2. NaN survives `mix(..., 0)`.** `mix(b, a, 0) = b + (a − b)·0` is NaN if `a` is NaN. With branchless code both
sides are always evaluated, so guard divisions everywhere: roofs have no wall run → `runLen = max(run.y, 0.01)`;
`max(fwidth(x), 1e-4)`; `max(yhi − ylo, 0.01)`; `max(sun.y, 0.05)`; for `(a − b)/x` near x = 0 pick a safe
divisor first (`xs = mix(max(x, 1e-3), min(x, -1e-3), f01(x < 0))`, night.js `hazeDepth`).

**3. `If` branches are fine when their nodes are their own.** For rare, costly terms (night shopfronts, roof lamps,
obstruction lights) `Fn(() => { const e = base.toVar(); If(cond, () => { e.addAssign(term); }); return e; })()` saves
work on pixels that skip them — but build each term's nodes *inside* its branch (or as closures called there) and
never share a node between branches. Each branch skipped by whole buildings/bands saved ≈¼ of the night facade cost.

**4. Derivatives only in uniform control flow (WGSL).** `fwidth`/`dFdx` inside an `If` fails on WebGPU. Take them
before the branches and `.toVar()` them (rooftops.js computes `fwidth(vL)` first, then branches per material).

**5. Reversed `smoothstep` edges are undefined** in GLSL and WGSL (`edge0 >= edge1`). Use
`below = (lo, hi, x) => 1 − smoothstep(lo, hi, x)`. (Some reversed calls still in facade/water/cars.js happen to work
on current Chrome; don't write new ones.)

**6. Hashes of world coordinates lose precision.** Cell coordinates reach a few 100k (±50 km in metres, finer
cells more); fed into a float hash seed they lose precision. Wrap cell indices to 16 bits and mix as `uint`:
```js
const OFF = 65536 * 16;
const hashI = (ix, iz, salt = 0) => hash(mod(ix.add(OFF), 65536).toUint().mul(uint(0x9E3779B1))
  .bitXor(mod(iz.add(OFF), 65536).toUint().mul(uint(0x85EBCA77))).add(uint(salt * 0x27D4EB2F >>> 0)));
```
When one hash must serve several values, stretch its low digits by different primes (`fract(h * 97)`, `fract(h * 389)`).
Put the level into the hash when blending group sizes, else a 2-group and the 1-group at its corner share a value.

**7. Move per-object work to the vertex stage.** Values constant over a building (lit share, zone width, lamp
colour mix, crown colour) as `varying(...)` of per-vertex data: a few % of the night frame. The night fog's
closed-form haze integral is per vertex too (per pixel it cost a few %).

**8. JS loops unroll.** Worley 3×3 neighbourhoods, 5 wave layers, 4 mirror taps are JS loops generating TSL: keep
them small, branchless (`best = mix(best, d, f01(d < best))`), and count texture reads (water ≈ 22 per pixel).

**9. `THREE.Color(hex)` stores linear.** It parses hex as sRGB and converts. To pack sRGB bytes into an attribute,
convert back (`new THREE.Color(hex).convertLinearToSRGB()`) or parse the hex yourself (`parseInt(h.slice(1), 16)`);
unpack in the shader with `pow(rgb / 255, 2.2)`. Data textures (slopes, SDFs, atlases): `colorSpace = NoColorSpace`.

**10. Custom per-type tables.** Constants per instance type: a `select` chain over a few values, or
`uniformArray(vec4s, 'vec4').element(int(type))` for larger tables (cars.js far boxes and shadows).

## Depth, draw order, coplanar layers

**11. Depth over 2 m – 120 km: reversed float depth, not logarithmic.** A logarithmic depth buffer writes each
fragment's depth from the shader, which switches off early-Z: all overdraw runs the full fragment shader. In Paris
(1 km tiles, courtyard blocks, walls in arbitrary order) that was 4–5× the facade cost (street at night 1,053 →
212 ms once reversed). A depth-only pre-pass does not help while the main pass itself writes fragment depth. Use
`new WebGPURenderer({ reversedDepthBuffer: true })` on WebGPU (keep log depth on WebGL 2 without `EXT_clip_control`),
and convert depth reads with the reversed-aware helper:
```js
// this runs in the post-processing output pass: give it the SCENE camera's near and far (11b), not cameraNear/cameraFar
const near = reference('near', 'float', camera), far = reference('far', 'float', camera);
const raw = prePass.getTextureNode('depth').sample(screenUV).r;
const viewDist = (renderer.logarithmicDepthBuffer ? logarithmicDepthToViewZ(raw, near, far)
  : perspectiveDepthToViewZ(raw, near, far)).negate();
const aoFar = smoothstep(3000, 6000, viewDist);   // SSAO faded out 3–6 km (it drew horizontal bands far away)
```
Two more places assume 0-to-1 depth (three r186): (a) **the shadow lookup** counts a point as inside the map when
its depth there is `<= 1`, which with a 0-to-1 depth leaves out what lies beyond the shadow camera's far plane, but
with reversed depth (far = 0, beyond it negative) lets it through to a compare against the cleared map: shadowed.
Paris's overview showed a sharp-edged dark quadrilateral several km across where the ground lay beyond the sun's
far plane. Keep those points lit with a shadow filter (`main.js`):
`sun.shadow.filterNode = (i) => select(i.shadowCoord.z.lessThan(0), float(1), PCFShadowFilter(i))`. (b)
`Frustum.setFromProjectionMatrix(m)` defaults to WebGL, non-reversed: pass `camera.coordinateSystem,
camera.reversedDepth` when culling against a rendered camera's projection (the default only loosens the far plane,
but say what the matrix is). Anything a sky pixel reads from depth sees the reversed clear value 0, not 1.

**11b. Inside a pass, the camera nodes are the pass's own camera, not the view's.** `cameraNear`, `cameraFar`,
`cameraPosition` and the camera matrices resolve to the camera of whatever is being rendered. In a material drawn
by the scene that is the view camera; in a node evaluated by the post-processing pipeline's output pass it is the
full-screen quad's orthographic camera (near 0, far 1). The ambient-occlusion far fade was written with
`perspectiveDepthToViewZ(raw, cameraNear, cameraFar)` in the output pass: every distance came out about 0, the fade
never started, and the occlusion's depth noise drew faint vertical streaks over Hong Kong's hills and evenly spaced
horizontal stripes across the haze over Fuji in Tokyo, for weeks, in every city (switching the occlusion's
intensity to 0 made both vanish). Fix: pass the scene camera's values in explicitly,
`reference('near', 'float', camera)` and `reference('far', 'float', camera)` (or uniforms updated per frame), as
`main.js` does (`ao.cameraDepth`, on by default). Verify any distance-based fade with a view **beyond** its far
distance: if nothing changes between a view inside the fade and one past it, the distance is wrong.

**12. A huge plane can't reliably lose depth to land 1 m above it.** The 400 km sea quad z-fought with the coast.
Make it a depthless backdrop: `sea.material.depthWrite = false`, `sea.renderOrder = -1`, and `sky.renderOrder = -2`
(the sky first of all, or it paints over the depthless sea). Re-apply `depthWrite = false` whenever the sea's
material is replaced (main.js does it after `createSeaMaterial`, and the sea's lit copy copies `depthWrite`).
Everything else draws over it; the land meets the sea at y = 0 vs −1.

**13. Coplanar layers: lift in metres, consistently across pipeline and viewer.** Ground layers are draped over the
same TIN. Offsets used (keep one table and reference it from both sides):

| Layer | y offset | Notes |
|---|---|---|
| sea plane | −1 | depthless backdrop |
| mud (tidal flats) | −0.5 | between sea and land |
| land | 0 | |
| coast strips' land side | +0.75 | over land and green, under roads; toe band over the sea at −0.96, transparent, no depth write, `renderOrder 1` |
| green | +0.6 | |
| inland water | +0.9 | |
| aeroway | +1.2 | |
| roads | +1.5 | baked by the pipeline |
| markings | road + 0.12 | sidewalks road − 0.12, so any road running into them covers them |

`polygonOffset` is not a substitute under log depth at kilometre distances; metre-scale lifts are invisible from
normal views. Water surfaces mirror at one plane (y = 0) serving −1 and +0.9 (1–2 m off is not visible).

**14. Transparent overlays over water:** `transparent: true, depthWrite: false`, explicit `renderOrder`; the planar
mirror target is cleared to transparent black and sampled premultiplied (alpha says where something is mirrored).

## Quantized attributes and packed data

**15. gltfpack drops texture coordinates no texture uses (or loses their scale).** The facade data rides in UV sets
with no texture. Quantize in the pipeline yourself (KHR_mesh_quantization) with **fixed ranges** exported to the
viewer (`tiles.json` `uvRange`, e.g. `uv [4096, 4096]`, `fac [16, 1024]`, `base [1024, 1]`), and scale back in the
shader: `const run = uv(0).mul(vec2(uvRange.uv[0], uvRange.uv[1]))`. Use meshopt through its Python bindings and
check every buffer round-trips.
Our own writer did the same once: `write_glb` wrote texture coordinates for buildings only, so the bridge cables'
uv (distance along, a marker) never reached the viewer and New York's necklace lights never showed, however
the shader was tuned. When an effect doesn't show, first check its attribute is in the loaded geometry
(`mesh.geometry.attributes`).

**16. Packing several values in one float:** style id + seed as `code = id + seed * 0.999` →
`style = floor(code + 0.0005)`, `seed = fract(code + 0.0005) / 0.999`; integer channels in a normalized colour:
`c = floor(vertexColor() * 255 + 0.5)`; bit flags with `mod(floor(v / b), 2)`. Keep a small epsilon against
quantization rounding.

**17. Quantized positions are undone by the node's matrix.** Reading positions on the CPU (terrain lookups, shore
raster, parapets from walls) must apply `matrixWorld` (`x * e[0] + e[12]` for axis-aligned scale + translation).
Ground positions at 14 bits had ~4.6 m steps: use 16 bits on one lattice for large extents; things placed in the
viewer on such ground can sit cm off on slopes (trees sunk 0.3 m).

## Render objects, caches and shader lifetime

**18. What rebuilds a shader.** A render object is per mesh × material × pass (render context). On reuse three
compares its cache key: material cache key + a *dynamic* key = hash(`nodes.getCacheKey(scene, lightsNode)` — the
scene's environment, fog and lights —, `receiveShadow`, `renderer.contextNode.id/version`, array camera). A mismatch
disposes the render object and builds a new one. So:
- **Replacing `scene.fogNode`, toggling a light's `visible` (sun ↔ moon), changing the environment** → every
  affected render object is rebuilt (new shader build + pipeline). Changing *uniform values* (fog density/colour
  through `reference()`, light intensity/colour) does not.
- A **material `version` bump** (`needsUpdate`) re-checks the key.
- **Built shaders are dropped once no render object uses them**, so switching back rebuilds them again.
- Instanced and non-instanced meshes, different attribute layouts (itemSize, array type, normalized), shadow
  flags and renderOrder give different shaders (the `shaderKind` key in main.js).
Fix for day/night: hidden stand-ins per shader kind that keep both variants alive (`performance-and-loading.md`).

**19. Toggling `castShadow` off lost the shadows for good.** Shaders cached for daylight kept the shadow node three
disposes when a light stops casting. Use a second light (the moon, no shadows) and toggle `visible`.

**20. Changing a pipeline's `outputNode` recompiles its effect passes** (bloom: ~1.2 s). Build every variant once
(`RenderPipeline` per variant) and switch which one renders.

**21. Nested passes share the parent's render list.** The SSAO normals pre-pass runs inside the scene pass; hiding
the car group there crashed three. Empty the instances instead (`geometry.instanceCount = 0`, restored after:
`cars.without(fn)`), wrapping `prePass.updateBefore`. To freeze a pass (reuse last AO on animation frames), swap its
`updateBefore` for a no-op and restore it.

**22. The shader-preparation hook depends on internals.** `renderer._renderObjectDirect`, `_objects.get`,
`_nodes.getForRender/updateBefore/updateForRender/updateAfter/nodeBuilderCache`, `_geometries.updateForRender`,
`_bindings.updateForRender`, `_pipelines.get/getForRender(ro, promises)/isReady`, `_isPreCompiling`,
`backend.beginRender/finishRender/clear`, `_objects.createRenderObject` and a render object's `dispose`/`_bindings`
(the dispose guard, 40) — all private in 0.186.1. Pin the version in the import map; re-verify after
any upgrade (compare with three's own `compileAsync`).

## Lights, shadows, billboards

**23. Billboards and shadows.** Camera-facing cards cast their shadow facing the *sun*:
`castShadowPositionNode = place(sunRight, sunUp)`; shadow-pass masking with `maskShadowNode`; receive with lookups
moved sunwards (`receivedShadowPositionNode = positionWorld + sunDir * 0.8 * crownRadius`), or a crown shades
itself into blotches at shadow-map resolution.

**24. Specular glint strength.** `MeshStandardNodeMaterial` has a fixed 4 % F0 glint; coated glass needs
`MeshPhysicalNodeMaterial` with `specularColorNode` (`coat * f0 / 0.04`). Foliage with spherical normals needs
**no** specular (`MeshLambertNodeMaterial`), or crowns turn white against a low sun.

**25. Normals in custom materials:** give `normalNode` in view space: `cameraViewMatrix.mul(vec4(nWorld, 0)).xyz` or
`transformNormalToView(n)`. Non-uniform instance scale: divide the normal by the scale before normalising.

**26. Per-render uniforms.** Values that depend on which camera draws (main view, probe cube faces, the water
mirror's camera below the sea): `uniform(0).onRenderUpdate(({ camera }) => ...)`. The mirror camera is as far below
the plane as the view is above: use `|camera.y|` for height-dependent terms (the night haze used `exp(−h/100)` and at
−440 m drowned the mirrored city), and detect "in mirror" as `camera.position.y < 0` where a term must differ.

## Passes, targets, textures

**27. PMREM targets.** Re-render the sky environment into the **same** target (`fromScene(scene, 0, 0.1, 100,
{ renderTarget })`) so every `pmremTexture` node follows. For the city probe use **two** targets alternately (a target
can't be sampled while rendered) and re-point the nodes (`node.value = texture`). Captures take `{ size, position }`.
Hide the sun disc (`sky.showSunDisc.value = 0`) in captures, the light's specular draws the glint.

**27b. Guard any off-screen capture that is later prefiltered or blurred against NaN and infinity.** One bad
texel spreads: the glass's city probe (a 256 px cube capture of the city, then a GGX prefilter into mip levels) took
NaN and ±65504 (half-float infinity) from the road markings' night shader in a few probe faces; the prefilter smeared
them across whole mips, and Singapore's towers turned black or grew bright bloom orbs, a fault that carried across
later captures after many changes of light (a fresh capture cleared it). Fix (`facade.js`): a guard pass between the capture and
the prefilter that writes non-finite or negative values as 0 and clamps the rest (to 256: brighter than any lit
window, far below half-float overflow); and recapture once the pipelines that were still compiling during the first
capture are ready (41). Test with a sequence of light changes (day, dusk, night, day, 6–8 steps): a bad value
often appears only after one particular change. Any capture feeding a mip chain, a blur or bloom needs the same
finite-and-clamp copy.

**28. Partial render for the mirror:** `mirrorCam.setViewOffset(W, H, x, y, w, h)` renders only the water's screen
rectangle into a smaller target; mirror position, look-at point and up vector in the plane (the image comes out
flipped left-right: undo in the lookup). Size targets in 64 px steps so they aren't reallocated every frame.

**29. Read-back orientation differs.** `readRenderTargetPixelsAsync` returns the bottom row first on WebGL and the
top row first on WebGPU. Detect from content (trees.js checks where the trunk is) rather than by backend.

**30. Custom mipmaps:** `tex.mipmaps = [...]; tex.generateMipmaps = false` (coverage-preserving foliage mips, LEAN
slope mips work with the auto ones since averaging is linear in slope and slope²).

**31. Alpha-tested cards under MSAA:** `alphaTestNode` + `alphaToCoverage = true`; dithered LOD fades with the same
screen-door threshold on both LODs so fragments are exact complements:
`dither = fract(52.9829189 * fract(dot(screenCoordinate.xy, vec2(0.06711056, 0.00583715))))`, `maskNode = fade < dither`.

**32. Fog on a custom material.** A node material honours `scene.fogNode`; to do something special (the sea fading
into the sky's horizon colour), set `mat.fog = false` and fold the fog into `outputNode` yourself with the same
formula, reading the live density via `uniform(fog.density).onRenderUpdate(() => fog.density)`. `SkyMesh` ignores
fog. Custom fog: `scene.fogNode = fog(reference('color', 'color', scene.fog), factorNode)`.

**33. Pixel-ratio changes resize every pass target** (SSAO, bloom, MRT). Don't flip resolution for frames that don't
need it (redraws stay at the current state).

**34. `SkyMesh` goes dark within 1–2° of sunset** (Preetham): add a hand-tuned twilight over its `colorNode` for dusk.

**35. WebGL-only stall:** with `KHR_parallel_shader_compile`, three's `_completeCompile` can still take ~250 ms when a
background compile finishes. WebGPU (`createRenderPipelineAsync`) has none. Measure both backends.

**36. Don't sample a pass's depth texture from the scene's materials.** New York's scene materials read the
SSAO pre-pass depth for an occlusion fade. In passes where that texture was also the depth attachment, WebGPU
raised a usage validation error, and three's async pipeline creation failed for whatever it was building at
that moment: cars, facades, shadows or the glass probe went missing at random. Use the fragment's own view
depth instead.

**37. `SSRNode` (r186) needs a roughness node**; without one its shader fails with a null error. It gave blocky
smears on tower glass at half resolution anyway (`materials-and-realism.md` §3).

**38. `PMREMGenerator.fromScene` keeps a stale projection (r186).** Every generator renders with one shared
`PerspectiveCamera`; `fromScene` sets its `near` and `far` but never calls `updateProjectionMatrix()`. The renderer
rebuilds the projection once, at the camera's first render on WebGPU (switching its coordinate system), with
whatever near and far were set at that moment; on WebGL 2 it is never rebuilt (the constructor's 0.1–2000). In
New York the first `fromScene` was the sky map's (far 100), so every later city capture was clipped at 100 m:
glass mirrored bare sky and towers wore a light-blue coat on WebGPU only, and on WebGL 2 the capture silently
stopped at 2 km. Symptom to look for: the capture's triangles are drawn (`renderer.info`) but only the nearest
objects appear. Fix (facade.js `capture`): wrap `renderer.render` for the duration of `fromScene` and call
`camera.updateProjectionMatrix()` on each perspective camera it renders with.

**39. Two passes can share their render objects (r186): render contexts are keyed by format, not by target.**
`RenderContexts.get` keys a context by the target's texture count, format, type, samples, depth and stencil, its MRT
and the call depth, so two `pass()` nodes with the same settings (4 samples, no MRT, both nested one level deep in a
pipeline) get the *same* render context, and three's render objects (mesh × material × render context × lights) are
shared between them. Harmless while the two passes draw alike; but `renderer.contextNode` is part of the render
object's dynamic cache key, and a pass with its own `contextNode` (`scenePass.contextNode = builtinAOContext(...)`)
swaps it in. Each time a frame used the other pass, every render object of the view was stale, disposed and made
again. Paris M9 round 3: the occlusion pipeline's scene pass and the glow's still pass, alternating after dark at a far
view (moving frames through one, settled through the other): 408 render objects at once, a 10-15 s task. Fix: give
the pass with the special context a render context of its own, `scenePass.setMRT(mrt({ output }))` (same output,
another MRT id). To find such a thing, log the parts of the cache key per render object at creation and when
`RenderObjects.get` replaces it (a small CDP script: material key, `lightsNode.getCacheKey(true)`, environment and fog
node keys, `contextNode.id:version`, receiveShadow); the changed part names the cause. (SSAONode's own two quads
change their material key every frame by design; ignore those.)

**40. Disposing a render object that was never built builds it (r186).** `RenderObject.dispose` →
`Bindings.deleteForRender` → `getBindings()` → `getNodeBuilderState()` builds the whole node material only to destroy
the bindings it made: 37 ms for an average material, ~80 ms for a facade. A lazy build budget leaves many render
objects created but unbuilt, so a change of key (39) then cost 13 of the 15 s inside `RenderObjects.get`, before any
budget. main.js wraps `_objects.createRenderObject` so a render object without a node builder state
(`_nodes.get(ro).nodeBuilderState === undefined`) is given `_bindings = []` before its dispose.

**41. A render object whose pipeline is still compiling is skipped silently (r186).** With asynchronous pipelines
(`createRenderPipelineAsync`, `KHR_parallel_shader_compile`), `Pipelines.getForRender` hands back the pipeline made in
an earlier frame, adds no promise, and `isReady(ro)` stays false until the driver is done: the renderer just doesn't
draw it. A lazy loop that counts a frame as complete when it built nothing new and got no new promise (main.js
`lazily`) therefore calls a frame complete that left out everything still compiling from the frames before. Paris M9
round 4: after a night start the first "complete" Day frame at the Cité drew a handful of objects, the cover went, and
9 frames with gaps (80-250 draws) followed. Count a not-ready object as left out (`prep.skipped`), but don't wait
on it: the frame that asked for it already holds its promise and redraws when it resolves.

**42. The shadow pass's render objects are the meshes' own and come back at the first frame in daylight after a
night start (r186, open).** After a night start (moon on, sun hidden, no shadow pass) the first Day built the
ShadowMaterial of every caster kind again (town 80-120 ms, buildings ~50 ms, ~0.35 s in all), although the warm-up had
drawn the stand-ins into the sun's shadow map in day light; also when a dry settled pass of the real view had been run
in day light through a blinded camera (view camera on an empty layer, the shadow camera kept its own: three copies
the view camera's layers into the shadow camera unless that has one beyond layer 0). Not found: what in their key
differs at the first real Day frame. The stand-ins' shadow pass still helps (their pipelines are compiled: the first
Day at the Cité 1.6-1.8 s behind the cover with it, 2.5-3.0 s without; 0.4 s at the overview), so main.js keeps it.

- **A `Fn(() => ...)()` branch captures JS variables lazily.** Its callback runs when the shader is built, not
  where it is written: `wall = branchOut.xyz` after `const branchOut = Fn(() => { const V = { wall }... })()` makes
  the branch read its own output, three warns "Recursion detected. VarNode" and the material draws nothing
  (London M4: every building vanished, only rooftop items floated). Take the inputs into a `const` object before
  the `Fn` and copy those inside.
- **Never switch a light's `castShadow` off to hide its shadows.** three r186 disposes the light's shadow node and its
  depth texture while the cached shaders still sample them: switched on again, `ShadowNode.updateShadow` throws
  ("reading 'depthTexture'"), WebGPU reports the destroyed ShadowDepthTexture in a submit, and nothing reaches the
  canvas after that (the menu's Shadows switch, every city, until the warm-up fix's follow-up). Keep `castShadow` on;
  set `light.shadow.intensity` to 0 (a uniform: no rebuild, every lookup returns lit) and skip the shadow pass
  (main.js `setShadows`: `needsUpdate` reads false while off). Measured: 10 switches in Paris and New York, 10 in
  Berlin (WebGPU) and 4 in Berlin (WebGL 2), no error, every frame drawn, shadows-on shots bit-identical to the first.
