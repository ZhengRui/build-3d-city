# Materials and realism

How each visual layer of the viewer was made to read as real, with the parameters that worked and the feedback or
failure that led there: first in Shenzhen, then refined city by city (each lesson names its city). Code:
`engine/viewer/*.js`; per-city values in each example's `web/city.json` (`../examples/`). Numbers are starting
points for a new city; colours are linear RGB unless marked sRGB.

The user's framing, once the geometry was right: *"next is using three.js to imagine the photo-realism details, it
doesn't have to be that accurate."* Plausible, consistent, never shimmering — not surveyed.

## 0. Principles that applied everywhere

- **Procedural TSL, no textures** (except small generated ones: wave slopes, leaf atlas, impostors). Everything is
  a function of world position, wall-run coordinates `(s, y)`, road coordinates `(across, along)` or per-vertex
  data from the pipeline. Scales to 200k buildings with zero texture memory and no seams between tiles.
- **Filter by pixel footprint.** Every pattern knows its size on screen (`fwidth`) and fades to its mean before it
  gets smaller than a pixel: box-filtered stripes (exact integral of a periodic pulse), fbm octaves faded to 0.5 as
  they shrink, variation moved to ever larger groups of cells. The recurring failure modes were *shimmer*,
  *moiré/stripes* and *pixel mosaic*; all came from detail below ~2–4 px. Check at 2× dpr (the user's screen).
  ```js
  // share of [t - w/2, t + w/2] where fract(t) is in [lo, hi]: sharp when big, its mean (hi - lo) when sub-pixel
  const stripeInt = (t, lo, hi) => floor(t).mul(hi.sub(lo)).add(clamp(fract(t), lo, hi)).sub(lo);
  const stripe = (t, lo, hi, w) => stripeInt(t.add(w.mul(0.5)), lo, hi).sub(stripeInt(t.sub(w.mul(0.5)), lo, hi)).div(w);
  const resolved = (fw, freq = 1) => float(1).sub(smoothstep(0.3, 0.9, fw.mul(freq)));   // 1 sharp .. 0 sub-pixel
  ```
- **Reflections are added as emission** (`emissiveNode = reflected * fresnel * ...`), not through `envMap`: walls
  and roofs keep the scene's plain sky light instead of the environment's much stronger diffuse term, and each
  reflection can be dimmed, desaturated and soft-clipped on its own.
- **Tone mapping: Khronos PBR Neutral, exposure 0.9.** ACES shifted hues and crushed the haze. Neutral's toe removes
  most of the smallest channel from dark colours, so dark greens turn saturated yellow-green: keep blue in greens
  (≈ half of green) and desaturate foliage before lighting.
- **Everything follows the live sun** (`uniform(sunDir)` shared object, not a copy): the time slider must relight
  tree crowns painted on the ground, rock facets, water body colour. A fixed copy was a bug found at 8:00/17:00.
- **Randomness is deterministic** (hashes of position/ids, seeded RNGs), so every load and screenshot match.
- **Daytime shaders never pay for night.** Lit variants are separate material copies (section 13).

## 1. Sky, haze, light

| Item | Setting | Why |
|---|---|---|
| Sky | `SkyMesh` turbidity 6, rayleigh 1.6, mie 0.006, g 0.8, cloudCoverage/Density 0.55 | scattered fair-weather cloud; clouds also appear in reflections via the env copy |
| Haze | `FogExp2` density **7e-5**/m (¼ at 8 km, most by 20 km); colour **HDR (1.05, 1.18, 1.35)**, as bright as the horizon before tone mapping | an LDR grey fog ended the land in a grey band; HDR haze melts land and sea into the sky |
| Altitude | density × `min(1, 1500 m / camera.y)` | haze sits in the lowest 1–2 km; from high up the city must stay visible |
| Far thinning | custom `fogNode`: beyond 9–22 km view depth, density ÷ (1 + y/700 m) | far hills (Hong Kong, Wutongshan) stand above the haze as they do from the city; plain melts |
| Sea haze | the sea applies the same FogExp2 itself and fades into the sky's horizon colour beyond 20–70 km at grazing angles | no seam where the 400 km quad meets the sky |
| Sun | 4.0 × smoothstep(elev, −2°, 12°); colour (1, 0.72+0.23k, 0.5+0.36k), k = smoothstep(elev, 2°, 30°) | warm, weak low sun |
| Hemisphere | 0.35–1.1 by elevation; haze colour × (0.3 + 0.7 smoothstep(elev, −2°, 25°)), warmer low | haze lit by the same sky |
| SSAO | settled frames only; radius 18 m, intensity 3, half resolution; darkens ambient via `builtinAOContext` **and** the final image by `mix(1, ao, 0.45)`; faded out 3–6 km | alleys, courtyards and building feet; the sun's shadows alone looked flat. Final-image darkening is an artistic compromise (sky light is weak next to the sun) |

## 2. Facades (`facade.js`)

**Write a new facade pattern behind its own shader branch from day one.** Every pattern added to the one facade
shader costs every pixel of every wall, mostly on WebGL 2, where the branchless code runs in full: Singapore's and
Hong Kong's new patterns made WebGL 2 street-level frames 25–45 % slower until they moved into branches taken only
where the pattern draws (`facade.patternBranch`, `billboardBranch`, `bayFade`, `night.glowBranch`; see
`tsl-and-three-pitfalls.md` 1 on making branches safe). Measure WebGL 2 at street level the same day a pattern goes
in (`scripts/speedtest.mjs --webgl`), not at the performance milestone.

Per-vertex data from the pipeline (quantized into fixed ranges, `index.uvRange`):
`color.rgb` wall colour or glass tint, `color.a` bay module; `uv0 = (distance along the wall run, run length)`;
`uv1 = (style id + seed, building height)`; `uv2 = (base height)`. Height in the shader = `positionWorld.y − base`;
roofs = `normalWorldGeometry.y > 0.9`. Styles: glass, residential, village, factory, commercial, civic, plain
(plant rooms), and landmark skins fins, bands, lattice, honeycomb, panel.

- **Whole bays and floors:** `bays = max(1, round(runLen / bayNominal))`, `X = s / (runLen / bays)`;
  floors `fh = height / max(1, round(height / floorNominal))`. Nominal bay (m): glass 1.5, residential 3.4, village
  2.7, factory 6, commercial 4.2, civic 3.6 (×0.85–1.2 per building); floor heights per style from the pipeline
  (≈3.0–5.0 m). Windows never get cut at corners or the roof line.
- **Openings** as fractions of a bay/floor per style (e.g. residential x 0.2–0.8, y 0.3–0.86); ground-floor
  shopfronts/lobbies (residential, village, commercial); balconies on 35 % of residential columns with a railing
  band; aluminium frames white or dark per building; AC units under 45 % of village windows, 28 % residential;
  weathering streaks under windows, grime in the lowest 3 m of villages/factories, per-bay ±3 % variation; a
  parapet band 0.7–1.2 m below the top.
- **Far away** (window cell below ~0.12–0.35 px): the window grid fades to its average colour
  (`mix(wall, darkGlass, cover*0.85)`) instead of shimmering.
- **Roofs:** concrete (villages darker), factories blue (45 %) or grey steel; 1.5 m noise cells.
- **Zinc cities (Paris roofs round):** one zinc tone per city (±15 % per roof) read as "one grey carpet" from 1 km.
  What made the aerial mosaic: each roof its own brightness over a wide range (0.7-1.42 × the zinc colour, the
  pale ones greyer: new silvery zinc against old blue-grey), 15 % slate (mid charcoal: at linear 0.07 it read as holes
  and navy), a darker brisis, 7 m patches faded with distance, a few glazed courtyard covers, planted beds and decks
  over part of a flat roof (a whole roof green read as a lawn), and the chimney pots' warm speckle kept beyond the
  pots' own range as a pot-coloured band on the stacks (`rooftopLook`). Mean brightness unchanged, settled frame
  unchanged (all per-roof constants and hashes in the existing branch).
- **Red-tile cities (Berlin M4):** colouring a roof shape's whole top in its tile turned the Altbau districts into
  a sea of orange from the air. Berlin's Berliner Dach is a steep tiled street slope in front of a flat tar-paper
  top: `facade.roofs.flatTops` draws the flat tops in the flat roofs' tones and keeps the tile on the slopes, which
  gives the real aerial look (red rims round grey roofs); the tile itself pulled from the sampled sunlit #b25938 to
  a darker brown-red (linear 0.26/0.1/0.058) with `tileAge` 0.6 (weathered to brown-grey, each roof its own amount),
  and slate neutral grey (`roofs.zinc`), not Paris's blue zinc. Pastel re-clad Plattenbau and red brick read
  candy-coloured and orange in the low October sun at the sampled values: muted and darkened, as London's brick.
  The M4 critic then found the opposite: all tops grey and 40 % of the slopes slate read "slate and tar" from the
  air, where Kreuzberg's aerials are a red-brown carpet broken by grey flat roofs. The balance (M4 fix round):
  `flatTops` as a share (0.45: the rest's tops tiled, the Berliner Dach's low courtyard slope), 85 % of the Altbau's
  roofs tile (`[facade.berlin] tile_old`), `tileAge` 0.45. Chimneys: Paris's and London's rows of terracotta pots on
  tall stacks are wrong in Berlin: short (0.6-1.3 m) brick or plastered stacks under a cover slab
  (`[rooftops] stack_cap`).
- **Eye-level Altbau (Berlin M4 fix round):** flat painted walls read as stage sets at street level. What made them
  read as stucco fronts, all in the shader: a profiled cornice (consoles, the soffit's shadow, dentils, a corona, a lit
  top moulding) and string courses with their shadow lines, faded by the floors' size on screen alone (along a
  street the fronts are at a grazing angle: their bays a pixel wide, their floors tens of pixels high, and the
  receding cornices are what the eye follows); window surrounds with a shaded reveal and hood, an aedicule with a
  pediment on the Beletage; white Kastenfenster with a meeting stile and a transom, net curtains and drapes behind
  half the panes (black panes read as holes); balconies with iron railings on the middle or outer bays; lit shop
  interiors, name boards with letter glyphs and awnings (dark boards read as black bands). (Moving frames once left
  the stucco, curtains, awnings and railings out, `facade.movingDetail` false: removed, the detail is drawn in every
  frame.)

## 3. Glass and the city reflection — the longest feedback loop

| Round | What the user saw | Cause | Fix |
|---|---|---|---|
| 1 | "the tall building's glass looks weird light blue" | glass reflected only a sky PMREM; from above it mirrors the bright horizon haze | below the horizon reflect a dim city tone (⅓ of the haze); per-pane tilt/brightness; darker body; refuge floors only on some towers |
| 2 | "tall buildings look like light blue blocks from far, no texture and mirror feeling" | a flat tint once panes are sub-pixel; no real surroundings in the reflection | **city reflection probe** + coated-glass model + pane variation that survives distance |
| 3 | "ahhh it's toooo glassy" | Schlick → full mirror at grazing angles of a saturated clear-sky model and an HDR horizon | cap grazing reflectance at 50 %, dim + desaturate the mirrored sky, soft shoulder, show the body tint, halve pane tilt/bow |
| 4 | "the reflection default 50 is a good default" | — | Reflections slider default **0.5** (×1 = physical) |
| 5 (New York) | "light blue cover, like a blurry segmentation mask" on most towers seen from above; a few dark | the city `lift` (0.6): a floor under what glass mirrors below the horizon. Nearly all of a real mirrored city is darker, so most of the reflection became one flat warm grey, which the coating turned pale blue | `city` 0 (the engine default); `reflectance` 0.6 ("a little too glassy" at 1.2) |
| 6 (New York) | switching between two places carried the old place's glass look into the first frames of the new one (blue to the next view, dark to the WTC), then jumped | the probe was recaptured only on the settled frame | a jump to a chosen view recaptures it for its first frame |
| 7 (London) | "every tall glass building the same near-black navy glass with one fine window grid"; the City's cluster is pale silver-grey and grey-blue in daylight | New York's `reflectance` 0.6 and dark tints: the body is a dark interior unless the tint passes the silver threshold (0.18-0.4 linear luminance), so mid blue-grey tints read navy | a pale palette (silver, green-grey, blue-grey, a bronze, dark one in twelve), `glass.silverFrom/silverTo` 0.06/0.3 so they read as coated silver, `silverDesat` 0.45 (else pale blue tints became light-blue blocks), `reflectance` 1.0, `skyDim` 0.75; `glass.variety`: four mullion rhythms and module widths per tower; named towers' own tints (22 Bishopsgate silver, the Walkie-Talkie pale with thin fins) |
| 8 (Singapore) | towers as uniform pale clay from the air, milky and matt | the `city`/`floor` lift raised again (to brighten dark low views), with the same result as round 5 | back to 0; fix dark low views another way (body tint, `grazing`). **Keep `city` and `floor` at 0**; a critic's artefact list should include "towers as uniform pale clay from the air" |

**City probe (`createCityReflection`):** on a settled frame, when stale, render the scene from a point
**110 m above the orbit target's ground** (or `0.8 × target.y + 30` if higher) into a **256² cube**, prefiltered by
its own `PMREMGenerator`; only tiles within **3.5 km**, trees/rooftops/cars hidden, sun disc off (the light's
specular draws the glint), fog at ground-level density, water mirror off. Stale when the probe point moved
> max(300 m, 0.2 × view distance) or 30 % in height, the sun moved, or tiles finished loading (`markStale()`).
A **jump to a chosen view** (`goTo`: a place button) recaptures it for its first frame (`probeJump` in main.js),
not only once the view settles: otherwise the first frames mirror the place left behind.
**Two targets in turn** (glass samples the last capture while the next is drawn — a target can't be read and
written at once); all `pmremTexture` nodes are re-pointed at the new texture. Cost: ≈280 draws, 6.2 M triangles,
20–30 ms CPU per capture, nothing while idle or animating.

**Parallax-corrected lookup:** the reflected world is assumed `PROXY = 600 m` away along the reflected ray (plus 4×
the pixel's distance from the probe, so far towers fall back to plain direction lookups), or on the ground plane if
the ray meets it first: `lookup = (P − probe) + r * min(reach, y / −r.y)`. Towers mirror neighbours and the street
at their feet with plausible distortion. Known limits: one probe per view (far towers approximate), a pop when the
new capture swaps in after settling far away, and the probe follows the orbit target, not the camera: a landmark
button aims up its tower while a drag leaves the target on the ground, so the same camera can capture from
points hundreds of metres apart and glass looks different by how the view was reached. A probe placed from the
camera alone (where the view's centre ray meets the ground) removed that, but it went in with other glass
changes, and New York's user preferred the earlier version's reflections and their steadiness while orbiting:
all of it was reverted, and this limit kept.

**Coated glass shading** (curtain walls):
- `f0` 16–36 % per building (silvery more, clear less; fins ×0.8), ±10 % per pane group; plain windows 5 %.
- **Capped Schlick:** `fresnel = f0 + max(grazing − f0, 0) * (1 − n·v)^5`, `grazing = 0.5`. Tower glass is never a
  perfect mirror (coatings, dirt, bow), so the body and interior still read at oblique aerial angles.
- Mirrored **sky part** (r.y > −0.1…0.03) desaturated 50 % and dimmed to 65 % (Shenzhen's haze; passes the coating
  twice); a faint haze (≤ a few % of the horizon colour over the reflected distance) — more washed every tower into
  the same pale blue; **soft shoulder** `c / (0.8c + 1)` so the HDR horizon can't turn grazing glass white.
- Coating tints the reflection towards the glass colour (35 % towards `tint / luminance(tint)`).
- Body: dark office interior (0.018–0.07, ×tint), roller blinds on some panes (light grey, part-way down), faint
  ceiling-light lines on half the floors (box-filtered), spandrels (glass over dark or light grey back panels),
  mullions (aluminium), refuge floors (≈55 % of towers > 150 m, every 10–16 floors, louvred, none at street level),
  a coping line at the top. Body × (1 − F).
- **Pane tilt and pillow:** each pane's normal tilted ±0.1–0.4 % (`waviness` 0.002–0.008 per building) and bowed
  (0.01 × paneNear), spandrels set differently; so reflections break up pane by pane and floor by floor. The sun
  glint uses the same normals and `specularColorNode = coat * f0 / 0.04` (needs `MeshPhysicalNodeMaterial`).
- **Variation that survives distance:** per-pane hash values (tilt, reflectance, blinds, interior) belong to groups
  of 2, 4, 8… bays and floors once panes shrink below a few pixels (`L = log2(max(fwidth(X) * 4, 1))`, blend between
  `2^floor(L)` and the next level, level in the hash), so distant towers stay mottled, never flat, never shimmering.
  Coarser groups tilt less (`0.6^level`). Lookup roughness and glass roughness grow as panes shrink (glint spreads to
  a sheen instead of sparkling on single pixels).
- Tunables live as uniforms in `mat.userData.tune` (`grazing 0.5, skyDim 0.65, skyDesat 0.5, soft 0.8, floor 0,
  city 0, reflectance 1, coat 0.35`; a city's `facade.glass` overrides them): tune live in the browser, show the
  user both extremes when taste decides. What they do from the air:
  - `reflectance` scales `f0`, the head-on share. Aerial views see nearly every face at a slant, where
    `(1 − n·v)^5` is large and the `grazing` cap decides: in New York 0.15 and 0.10 looked the same. For how
    glassy towers look from above, move `grazing` (or the Reflections slider), not only `reflectance`.
  - `city` and `floor` put a minimum under the reflection (a warm grey, or the horizon colour). Any sizeable
    value replaces most of the mirrored city with one flat tone, which the coating tints: the "light-blue
    blocks" and "segmentation mask" complaints. Keep them 0 unless low views go ink-black, then use the
    smallest value that fixes those and re-check a high view.
- **Debug a wrong look by switching terms off, not by tuning.** Set one uniform (or one term) to its neutral
  value at a time over the views that differ, and find the term that makes the difference before changing
  anything. New York's coat went through about seven guessed fixes (probe height, probe placement,
  normalising the reflection, a shade light, screen-space reflections, a sharper probe), each of which moved
  the problem to other views and was reverted; switching terms off found the `city` lift in one pass.
- **Screen-space reflections** (three r186 `SSRNode`, half resolution, on settled frames) were tried for sharper
  reflections: blocky smears down the towers, and a second control beside the Reflections slider. Dropped. So
  was a 512 px probe with half the blur ("too sharp"): the 256 px probe's softness suits aerial views.

**Landmark skins** (from the landmark CSV: style, tint sampled from photos, module, a style parameter in the seed):
fins (stainless, one side shaded; fin width in the seed), bands (spandrel strips), lattice (two diagonal member
families, share of white panels), honeycomb (hex cells, share of glass cells), panel (seams every module and 3 m, a
glass strip every seventh). Patterns run in map coordinates on roofs; fade to their average by `fwidth/cell`.

## 4. Ground (`ground.js`)

- **Urban land:** lots on a 60 m grid warped ±22 m by noise, each lot one of paving / concrete / beige / dark top /
  scrub / bare laterite (weights 40/30/18/6/4/2 %), ±6 % tone; 6 m slab joints (box-filtered), paver grain, stains,
  weeds at lot edges. **Keep lot contrast subtle** — strong contrast read as camouflage from the air.
- **Hillsides:** land not covered by a green layer but steep (1 − n.y > 0.012–0.04 ≈ 10°) or high (110–240 m) is
  scrub and woods, not paving (most of Hong Kong's hills had no OSM green).
- **Parks/woods (green):** Worley crowns every 6 m, radius 0.5–0.8 cell, present by a density field
  (18–105 % cover from 170 m fbm); crowns shaded as domes relative to flat ground (`n·sun / sun.y`), leaf clumps,
  per-tree hue, crown shadow offset sunwards; lawn between, dark understory under closed canopy. **Painted crowns
  only where instanced trees aren't drawn** (beyond 4.2–4.8 km or trees switched off: a `treesOn` uniform) — they
  doubled up with real trees ("no painted crowns under trees").
- **Lawn colour:** first version was saturated yellow-green ("fix the yellow-green grass"). Shenzhen lawns under a
  hazy sky are a cool muted green; the warm sun and Neutral's toe push anything with little blue to olive. Lawn
  base now `(0.042, 0.07, 0.036)–(0.08, 0.11, 0.055)`: blue ≈ half of green.
- **Painted crowns as a hex mosaic** (Paris M4 critic: "grass is a blotchy hex pattern"): with the nearest
  Worley point deciding which crown a pixel shows, packed crowns were cut along the Voronoi cells' edges.
  `crowns()` instead keeps, of the 3 × 3 neighbours, the dome standing highest here (`(1 − d²/r²)·r`, absent
  crowns never win): round discs overlapping bigger over smaller, lawn between.
- **Squares and forecourts** (Paris M4/M5: Notre-Dame's parvis read as brown soil, the Louvre's Cour Napoléon,
  the Étoile and the Grande Arche's parvis as the same grey-and-moss blotches): pedestrian areas cut out of the
  lawns fell through to the urban land's lots (scrub, bare soil, weedy edges). `[ground] paved` writes stone
  pedestrian areas (paving_stones, sett, concrete, untagged) and asphalt ones as layers `paved` and `asphalt`
  (`pavedMaterial`: pale slabs 1.2 × 0.8 m in running bond or 0.14 m setts per 150 m cell, city.json
  `ground.paved` tones); `ground.urban` sets the land's lot palette, the scrub and soil shares, weeds, stains and
  slab size (Paris: pale stone, no scrub/soil, weeds 0.15, stains 0.45, 1.2 m slabs).
- **Mangrove reserve:** a nature-reserve boundary reaching 4 km² over the bay was painted as lawn ("fix the mangrove
  area"). Pipeline: clip green to land except mangrove stands; tidal flats become a **mud layer** (y −0.5): grey-brown
  silt, glossy where wet, dendritic creeks from the zero set of domain-warped noise.
- **Airport:** 5 m concrete panels along the runway heading (154.3°; per city), joints, rubber and oil stains.
- **Town beyond the districts** (Paris M7): the painted roofscape past the Périphérique read as "an empty beige
  plain ... like farmland" with La Défense "alone in a field", ending in a straight edge. Real OSM footprints raised
  as flat-roofed block masses (06e_masses) with the ground between them drawn as paving, yards and gardens
  (calmTown), and a land cover map on the backdrop, made the city run to the horizon with no edge (overview +71 ms,
  +232 draws on the Iris Xe). Keep the roofs muted: saturated terracotta on every house read as orange confetti.
  At night the banlieue must stay dimmer, warmer and patchier than the city it surrounds: procedural street lamps
  beyond a real lamp inventory at the full rate glowed as wide pale bands brighter than Paris (city.json
  `ground.outerLamps` gain 0.3, warm tint); mass windows at ~0.3 x the hour's home share, half as bright, their
  mean once sub-pixel (a per-window hash sparkled as white confetti), walls ~0.55 x their day colour; the ground
  between masses at 0.35 of its night glow. Past the masses, WorldCover's built-up class as sparse warm dots
  (70 m grid, a third lit, kept about a pixel wide and dimmer as they grow) in the lit copy only (0 cost by day),
  so the land beyond is not pitch black and the ground area's edge draws no line.
- **Land cover backdrop** (Paris M7 fix): a 100 m colour map bilinearly magnified read as "blurred camouflage";
  50 m over the backdrop plus 20 m over the masses' zone (JPEG, 1.8 MB together) keeps rivers as sharp ribbons, and
  per-class detail from the map's own colour (field parcels on a grid turned per 2 km, town speckle, wood clumps)
  faded out with distance (9-22 km) and by `resolved()` before it can alias into a grainy haze band. The town layer
  between masses takes its gardens and trees from the 20 m map instead of noise.
- **Backdrop** (terrain beyond the ground area, to ~36 km): vertex colours (forest/town/lake) × large mottling
  (900 m and 140 m fbm); `maskNode = positionWorld.y > −1` so the coast is where it dips under the sea plane.

- **Lawn over the water and path ribbons** (London M5 fix round): OSM park and grass polygons run out over a lake's
  edge, and where the bank is higher than the levelled water the lawn wins (wedges of grass on the Serpentine):
  `[ground] green_off_water`. Park paths cut out of the green showed the land's urban lots as uniform grey ribbons:
  `[ground] path_layers` puts each path through the green on its surface's layer (gravel, asphalt, paved). Large
  squares as a patchwork of 150 m grey rectangles: `pavedStyle.cellTone 0` (slab-scale variation only). Lawns one
  uniform olive from the air: `ground.lawnStyle.patches` (50-200 m greener and drier patches).

## 5. Roads and markings

- **Road mesh** (merged per tile, vertex colour by class) and the **markings strips** (06b_markings.py, above the
  road by 0.12 m; sidewalks 0.12 m below the road top so any road running into them covers them) share one
  `asphaltFactor()` of world position (55 m resurfacing, 5 m blotches, 1.4 m repairs, 9 cm grain) and the road
  class colours, so they meet without a seam. Railways (warm vertex colour) get ballast.
- Markings material works in `(across, along)` metres with a per-vertex code (type, half-width, lane count,
  one-way/big/motorway bits, flags). Everything box-filtered (`pulses`, `line`, `span`).
- Dashes after the national standard (China GB 5768: 2/6 m small streets, 4/10 arterials, 6/15 expressways; all
  periods divide the along-wrap); lines 0.15 m (0.2 big); edge lines 0.3 m in; double solid yellow ±0.2 m on big
  two-way roads, single dashed yellow on small; yellow left edge on dual carriageways; zebra 0.5–4.5 m from the
  junction, stripes 0.45 m per 1 m; stop line 5.3–5.7 m on the approach side. Oil line down each lane centre,
  polished wheel paths, repaving patches whole lanes wide.
- **The half-lane bug:** lane dividers must sit at `x = k·laneWidth` (between lanes). `pulses()` already centres
  its lines on multiples of the period; the divider added half a lane on top, so dashes ran down lane centres
  *under the cars* ("the white traffic lines are not in the right positions"). The cars were right. Lesson: when
  two layers disagree, check which one follows the data (cars followed the pipeline's lane centres).
- Sidewalks: kerb 0.22 m, 0.3×0.6 m pavers (grey or brick-red blocks), tree pits every 8 m (width > 2.9 m), bike
  lane (> 4.4 m), tactile strip; medians: hedge with bougainvillea in dot clusters (not solid blobs); pedestrian
  streets: 0.9 m stone slabs; runways: threshold piano keys, aiming point 400 m, touchdown bars, rubber deposits.
- Pipeline fixes that were visual: sidewalks only on land (they covered water), buildings standing on
  carriageways/under viaducts dropped (user screenshot "buildings on the road").
- **UK-style markings (London M5; `[markings]` warning, kerb_lines, kerb_mouths, red_refs, bus_lanes, cycle_lanes,
  junctions, zebras; city.json markings bigCentre, kerbLines, busLane, cycleLane, nearside, dashes.warning).** A
  zebra at every junction arm (the NYC/Paris default) is wrong in Britain: junction arms take a stop line and stud
  lines where OSM has a traffic-signal node within ~25 m, a give-way line on the lesser road elsewhere, nothing on
  the greater; real zebras come from OSM crossing nodes (`crossing=zebra`, `crossing_ref=zebra`), drawn between
  junctions as their own strip with give-way lines, 2 m zig-zags along both kerbs and the centre, and Belisha
  beacons as tiny solid geometry in the markings mesh (no extra draw). The lane strip leaves a gap for each, so
  nothing overlaps. Kerb lines (double yellow, double red on red routes) are two 75 mm lines 0.16/0.31 m off the
  kerb: thin, but the box filter keeps them as a coloured haze far off rather than shimmer. The warning line is a
  flag on the last few dozen metres of a lane strip before a junction, not a shader distance (the shader can't
  know where the piece ends). New strip types and flag bits must leave the shader's output unchanged when all
  flags are 0 (other cities).
- **Signal-controlled crossings between junctions** (London M5 fix round: "crossings lost" at Trafalgar Square and St
  Paul's): only junction arms took signal markings; OSM's pelican/puffin/toucan and `crossing=traffic_signals` nodes
  mid-block were ignored. `[markings] signal_crossings` draws them as zebra strips with flag 1: two broken stud lines
  2.4 m apart, a stop line 1.7 m back on each approach half, zig-zags (London 492). Zig-zags run in whole 2 m marks
  from 3 m (`zigzag` per approach; TSM's standard 8 marks), the centre set only where the road has a centre line
  (`zebra.centreZigMin`), the Belisha globes lit (`zebra.globeGlow`: a dark 0.3 m globe vanished from 50 m).
  Note for critics: TSRGD's urban centre line is 2 m in 6 and the lane line 1 m in 6; the 4-in-6 line is the
  warning line before junctions, not a swapped centre line.

- **German markings, setts, the Berliner Gehweg and trams (Berlin M5; `[markings]` setts, sidewalk_style, trams;
  city.json markings bigCentre 'solid', giveWay 'teeth', zebra.mid/zigzags/signal/studs, busLane.legend, setts,
  sidewalk.style2, sidewalk.median, tram).** RMS: white 3 m strokes every 9 m (0.12 m; 6/12 on motorways), no edge
  lines on city streets, a single solid centre on big two-way roads; signalled arms take a stop line and the
  pedestrian Furt (two broken lines of 0.5 m dashes 4 m apart), give-way arms Haifischzähne; zebras only where OSM
  maps one, plain bars without zig-zags or beacons. Cobbled carriageways (OSM `surface=sett`, a fifth of Berlin's
  residential ways) are setts in rows with no lane paint. The three-strip Gehweg: mosaic setts on the kerb and
  house sides of a walkway of granite slabs or 35 cm plates, per way by class share. Trams (OSM `railway=tram`) are
  their own strip over the lane strips (so they run on through junction boxes): two grooved rails 1.435 m apart,
  the bed asphalt or setts on a carriageway (the track sampled against the roads' half widths), grass or ballast
  with sleepers off it (covering 06_tiles' ballast band). The markings are bundled into 07b_blocks: re-run it after
  06b_markings, or the viewer keeps the old markings (`?blocks=0` to check).

## 6. Water (`water.js`)

Before: "the trees and water are pretty much colour blobs"; ponds on Wutong Island looked like grey concrete (3×
too bright, tinted by the sea's colour, rough as the sea).

- **Waves as slopes, not heights:** two 256² tileable sum-of-sines slope textures (64 components, 3–48 waves per
  tile, one long-crested spread 0.3 rad, one choppy 0.75), `rg` = slope, `ba` = slope² — mipmaps then hold mean and
  mean-square slope, so **unresolved slope variance becomes roughness** (simplified LEAN mapping): the glitter path
  widens and far water goes smooth as in photographs, no shimmer. Plus `fwidth(slope)²/4`.
- **Five scales**, each turned, domain-warped and with its own wandering strength (gusts), alternating textures:
  197 m / 53.3 / 14.1 / 3.37 / 0.91 m tiles, weights 0.016–0.025. Removes visible tiling and diagonal lanes.
- **Motion:** each scale drifts down-wind at its deep-water phase speed `c = sqrt(g L / 2π)` (long waves outrun
  short ones, so the pattern evolves instead of sliding as one sheet); gusts at 3.5 m/s; slicks/wind streaks creep at
  0.25 m/s; offsets wrapped on the CPU so time can grow forever. Rivers/canals: **flow map** from the water polygons'
  outline edges (each outline vertex has two edges along the bank; axis averaged as a doubled angle; sign =
  downhill of the distance-to-sea field; fades where unsure), speed 0.7 m/s rivers, 0.4 tidal canals, ponds 0,
  two-phase cross-fade every 5 s so the pattern never stretches.
- **Shore field** (CPU, once, from `ground.glb`): 1024×1536 raster → signed distance to shore (±300 m and 0–8 km),
  **fetch** (open water upwind) and distance to the open sea. Fetch makes harbour basins, marinas and coves
  calm, dark and mirror-like (long waves need ~25 of their tiles of fetch to grow). It is averaged over 9 wind
  directions within ±45° (cos² weights, semi-Lagrangian sweeps with interpolation, half resolution): with only
  the wind's octant and the two grid axes, every pier cast a 1–2 km lee with straight hard edges, read as darker
  wedges and tile-aligned rectangles on the open sea and bright radial streaks far off (Singapore M3, also New York
  off Liberty Island, Shenzhen's Shekou breakwater). Debug: force the field's blue channel to 255 in-page and see
  whether a sea pattern goes. Distance to sea decides which
  inland water takes the sea's colour (river mouths, tidal canals). Connected pieces of the water mesh are tagged
  per vertex (`waterKind` = sea-linked, pondness from area / bbox-diagonal²).
- **Colours (albedo lit as flat water, × (1 − F))**: the body is lit as a flat surface whatever the wave normals
  do, else it "ripples like crumpled foil". Estuary silty grey-green-brown ≈0.08 (shore band (0.105, 0.106, 0.082),
  bay (0.08, 0.094, 0.078), offshore grey-blue), silt plumes; enclosed basins darker/greener; rivers
  (0.036, 0.046, 0.03); ponds/lakes (0.011, 0.024, 0.018) ≈ 0.02 with algae patches.
- **Fountain basins black** (Paris: the Tuileries' octagonal basins, the Luxembourg's Grand Bassin, the Louvre's
  pools): small ponds took the lake colour (≈ 0.02, deep and dark) and, off the mirror plane, the dark wooded-bank
  fallback. `waterBasin` (per vertex: pondness × under ~6,000 m², gone by 15,000) mixes in `water.inland.basin`
  (shallow water over a stone floor, Paris (0.05, 0.066, 0.064)) and drops the banks' darkening: the open sky's
  reflection instead. `water.inland.skyTint` gives turbid rivers' mirrored sky a little of the water's tint (the
  Seine read slate-blue; photographs show it green-teal, #234c4a at street level).
- **Sky reflection:** PMREM lookup by roughness, F0 0.02 Schlick with slope variance lifting facets; ×0.6, partly
  desaturated (hazy delta sky), Mie glow soft-limited to ~1.6 (a rough sea otherwise turned into white foil towards
  the sun; the glint itself is the light's specular, so it is shadowed).
- **Planar mirror of the city** (buildings, trees, bridges; sky/water/flat ground left out): the scene from the
  camera mirrored in **y = 0** into a half-float target, **only over the screen rectangle where water can be seen**
  (25×25 ray grid against the water raster; `setViewOffset`), ≤ half the drawing buffer and ≤ **560 lines** (moving:
  0.35 scale, ≤ 320 lines), sizes in 64 px steps, tiles within **9 km** (moving 4.5 km), none beyond 12 km, no pass
  without water in view. Sampled at the pixel's screen position shifted by resolved slopes and smeared vertically by
  unresolved ones (4 taps, blurrier mips as it roughens): crisp in ponds, a dark blurred band under the far shore on
  the bay. One plane serves the sea (−1) and plain inland water (0.9); water > 3–8 m above it (hill reservoirs)
  fades the mirror out and darkens toward wooded banks instead.
- **A river that leaves the extent is "the sea"** (London M5 critic, twice: "the Thames a dark slate mirror"): the
  shore field counts everything beyond the extent as open sea, so a river cut by the ground area's edge at both ends
  was sea-linked and drew with the sea's palette, roughness and full reflection; colour changes to
  `water.inland.river` did nothing. An inland city sets `water.inland.seaLink: false`. Check which palette a body
  actually takes (`mat.water.userData.nodes.seaness`) before tuning its colour.
- **Tidal river vs still docks** (London M5 fix round): a turbid tidal river is opaque khaki-brown with fine chop and
  faint smeared reflections, the impounded docks beside it grey-blue mirrors. `water.inland.riverReflect` (0.45: the
  share of the physical reflection kept; the body then shows at grazing angles too), `riverWaves` (1.0: the sea's
  chop instead of the sheltered 0.25); `inland.still` { maxArea m² (pieces smaller than it and not sea-linked: the
  docks, park lakes, canal basins), body, reflect (a gain over Fresnel: 2.5 read as a mirror from the air), waves,
  banks (the dark-banks share off the mirror plane: a park lake at 15 m, 11 m over the mirror plane, read as dark
  olive under 0.85) }. Defaults keep the old shader.
- **Night water: streaks, not static** (Tokyo M8, Hong Kong M8). After dark the mirrored lit windows should be
  vertical streaks with soft edges. Three faults turned them into a field of white dots ("like static") or a
  grainy sheet, each with an opt-in fix (`engine/viewer/README.md`, `water.night.*`):
  1. *The knee on the mean drops single lights.* The night mirror averages 8 taps along a streak and takes a knee
     off the mean; one lit window is one tap in eight, so it fell under the knee and only big lit masses mirrored.
     `tapKnee: true` takes the knee off each tap's luminance before the mean (colour kept); `peak` (the brightest
     tap's share) and `fres` (the lights' least Fresnel share) then shape them.
  2. *Pixel-level grain far off.* Wave slopes resolved a few pixels across moved each pixel's lookup and Fresnel on
     its own. `ripple` (the share of the fine ripples' slopes used for the lights' lookup; the rest counts as
     roughness), `blur` (read the slopes that many mip levels blurrier than the pixel's own), `soft` (extra blur
     of the night mirror) and `tilt` (under 1: long swells no longer carry a far bank's lit rows up and down).
  3. *High cameras.* From 200 m+ the Fresnel floor and the brightest tap made every far lit window a white dot,
     and in Hong Kong the boosted districts spread into an amber sheet. `steep: {at: [from, to] m, knee, gain,
     peak, fres}` blends to other values as the camera rises.
  Tokyo's values, a starting point: `{knee: 0.07, gain: 9, max: 0.6, streak: 32, tapKnee: true, ripple: 0, blur: 3,
  soft: 1, tilt: 0.3, peak: 0.3, fres: 0.06, steep: {at: [25, 200], knee: 0.14, gain: 6, peak: 0, fres: 0.06}}`.
  Check water at night from 20–60 m (the streaks) and from 300 m+ (dots or sheet), on both backends.
- Menu: Mirror (`?reflect-water=0`), Waves (`?waves=0`).

## 7. Shores (`shores.js`, strips from 05e_shores.py)

Typed from nearby OSM tags; bands across each strip with `(across, along)`:
revetment (promenade, granite coping, railing, **rock armour**: angular 1 m blocks from a second-nearest Worley
distance, each split into two tilted flat faces lit from the sun side, dark voids, wet algae/oyster band at the
waterline — the first version "read as cobbles"), quay (apron, wall with fenders), beach (dry/wet sand, swash),
mudflat (mangrove mud with channels, fraying seaward edge that never runs parallel), embankment (concrete, green
foot), pond bank (lawn/soil, boulders, lily pads), pond edge (granite coping in 1 m blocks), pools (turquoise,
deeper middle, caustic hint). The toe band lies over the water, transparent, depthless, `renderOrder 1`.

River quays (Paris, `[shores] quay_walls`): the terrain's own step, even one TIN cell wide, read as "sloping
faceted grass-and-grey embankments" with a sawtooth waterline (M3 critic). A `quaywall` run is real geometry: a
vertical face at the water's outline from under the water to the quay, pale limestone ashlar in 0.5 m courses of
staggered 1.1 m blocks, dark and green at the wet foot (across on the face = metres over the water), and an apron
of granite setts with a stone coping along the edge laid flat over the TIN's step. Seen in photos
(refs/area-seine-water-level, area-quais-bouquinistes): the walls are pale, nearly vertical, lower quays flat
paving 2-3 m over the water.

## 8. Trees (`trees.js`)

From "faceted lumps" / "colour blobs" to trees built the way real-time foliage is:
- **Leaf atlas drawn on a canvas at startup** (1024², 4×4 tiles): twig sprays of thousands of small leaves per kind
  (ficus, camphor, acacia phyllodes, blossom, mangrove) and a pinnate palm frond. Channels hold **brightness, blossom
  mask, hue jitter, coverage** — no colour; the colour comes per instance, so one atlas serves every tree.
  **Coverage-preserving mipmaps** (per tile, alpha rescaled so as many texels pass the 0.5 test as at full size;
  transparent texels take the cell's mean colour): crowns don't thin out with distance.
- **Near (< 280 m):** per species a crown of 50–90 **camera-facing leaf-cluster cards in lobes** (alpha test +
  alpha-to-coverage), trunk and a limb per lobe showing through gaps, banyan aerial roots; **spherical normals**
  (card normal = mix of lobe and crown directions, bent to the card corner) so a crown shades as a soft clumpy
  volume; baked occlusion inside/under the crown; translucency when seen against the sun. Palms rigid (grey column,
  crownshaft, 18–24 folded fronds).
- **Lambert, not Standard, for foliage:** with spherical normals the specular term turned every crown top white
  against a low sun (Fresnel → 1 at grazing). Also cheaper under 4–5 layers of card overdraw.
- **Leaf colour desaturated to 72 %** before lighting (Neutral tone-mapping toe made shade lurid yellow-green).
- **Impostors (280 m – 4.5 km):** each species rendered at startup from 9 elevations × 2 azimuths (256 px frames,
  MSAA, read back, reduced to 128 px, coverage mips on the CPU) into colour-code and normal atlases; one
  camera-facing quad per tree showing the **nearest** elevation frame, mirrored or not, lit with baked normals.
  Blending two frames blurred the crown and fattened its outline. Near ↔ impostor cross-fade over 45 m by
  **screen-door dithering with the same threshold** (fragments are exact complements).
- **Shadows:** cards turn to face the sun in the shadow pass (`castShadowPositionNode`), impostors show the sun
  their sun-elevation frame; shadow lookups moved 0.8 crown radii sunwards (`receivedShadowPositionNode`) so a crown
  isn't blotched by itself at shadow-map resolution. All trees cast (a band where casting stopped showed in woods).
- **Species/placement:** 7 species fitting the city (banyan, camphor-like, acacia, Bauhinia/flame, mangrove, royal
  and coconut palm) mixed per land class; street trees one species per road; 2 in 3 area trees take their ~40 m
  grove's species. Far dense stands thinned beyond 1.3 km (keep `max(0.22, (1300/d)^1.5)`, widened ≤1.8× to keep the
  canopy closed); **carpet** polygons (canopy colour per class) beyond 4.5 km and as the dark floor of closed stands
  from ~1 km (0.6–1.2 km fade) — nearer, its straight polygon edges showed between trees. Trees sunk 0.3 m (16-bit
  ground positions put them cm off the terrain on slopes).
- Result: 8 draw calls; tree triangles in test views dropped 1.5–11× (e.g. forest at 1.2 km 2.54 M → 0.23 M).
- **A city's own species set (Paris, M6):** city.json `trees.species` entries with a new name and `like` add a
  species built like an existing slot on its own atlas `tiles`; `drop: true` removes unused slots (palms,
  mangroves: neither baked nor drawn). Leaf `form` lobed (plane, maple), palmate (horse chestnut), needle
  (pines); autumn `turn` (share of sprays whose leaves take the species' `bloomPal` colours through the blossom
  channel). Keep turned colours dull and close to the leaf's value (bright ochre read as yellow blossom) and
  keep some green leaves in turned sprays. `bark2` mottles the bark (plane trees). Eight species, 3 bits in the
  kind byte (`census.species_bits`). Cost on a plane-lined boulevard: settled +10 %, moving +14 %.

## 9. Cars (`cars.js`)

- Seven types built at startup to the pipeline's dimensions (sedan, SUV, taxi with roof sign, van, bus, box truck,
  container lorry), ~200 triangles (lorry 460): a body **lofted through cross-sections** (bumper, hood, windscreen,
  roof, rear window, boot), octagonal wheels with hubs, light quads.
- One procedural material: paint in one or two colours (taxi roofs, bus liveries, containers with corrugation that
  fades 60–160 m), dark glass (f0 0.07, reflections ×0.45 so windows read dark from above), clear coat (f0 0.045),
  sky/horizon reflection like the glass. Palettes: mostly white/black/silver/grey; local taxi and bus colours.
- LOD: models < 320 m, painted 10-triangle boxes (window band, dark windscreen from above) to 3 km, dithered out
  over the last 500 m; lane ends fade over 4 m inside junction boxes.
- **Planar shadows** within 1 km: a convex hull (footprint, shoulder, roof) squashed onto the road along the sun;
  back-face culling leaves exactly one layer, one translucent draw (opacity 0.5 × sun strength), no stencil. Cars
  don't cast into the shadow map (it isn't redrawn while traffic moves).
- **Motion without simulation:** a car is a phase in its lane's loop, `p = (p0 + v t) mod P`, mapped through a
  speed profile that queues before signalled stop lines and accelerates after. Heading eases over the last 2 m
  before a bend. Only lanes within 1.5 km animate (a fraction of a ms per frame).
- **Model variants per city** (Paris M6): a type's optional fifth item in `[cars] types` names the viewer model —
  `hatch` (two-box Clio/208), `taxi_paris` (dark saloon, white roof light with a green/red lamp lit on moving
  taxis), `bus_idfm` (silver body, blue band along the roof side, blue rear), `moto` (scooter + rider, ~250
  triangles, 10-gon single wheels; the rider parts are masked out on parked ones, so one geometry serves both).
  Moving two-wheelers ride off the lane centre (±0.65 m by rank); parked ones stand across the kerbside row in
  bays of 3-5 (`moto_bays`). One more draw call per type.
- Cars are emptied (instance count 0) from the AO pre-pass (frozen AO would keep dark halos where cars were) and
  hidden from the water mirror (not redrawn on animation frames).

## 10. Rooftops (`rooftops.js`)

- Items from the pipeline by building kind (village stair boxes with tiled hats, stainless and blue plastic tanks,
  solar water heaters facing the equator, blue lean-to sheds, potted plants; tower lift boxes, pergolas, helipads
  > 100 m; office cooling towers, air handlers, window-cleaning cranes; mall unit rows, ducts, skylights, green beds,
  roof car parks; factory ventilators, skylight strips, solar rows) as instances of **five unit prototypes** (box,
  cylinder on a stand, tilted panel on legs, gable, leafy blob) with one procedural material per prototype that
  paints doors, louvres, fan grilles, evacuated tubes, PV cells, corrugation, tiles, helipad and parking marks.
- **Parapets built in the viewer from the building tiles' own walls** (a box along every wall's top edge, so it
  follows the rendered outline exactly): 0.9–1.25 m villages, 1.1–1.5 m residential/commercial/civic, glass screens
  1.8–3.4 m on 55 % of office towers, none on plant rooms, landmarks, or walls standing back to back with a building
  of about the same height (satellite footprints split buildings).
- LOD by size: small things fade from 420 m, tanks and parapets 900 m, boxes 1.6 km, large things 2.6 km (dithered
  over the last fifth). Only items that matter cast shadows. 6 draw calls, 0.1–0.2 M triangles over a dense village.
- **Roofs with a shape (mansards, pitched; Paris M6).** Items stand only on the roof's flat top as 06_tiles builds
  it (`extrude(..., roof_out=)`: the terrasson, a pitched roof's ridge strip), never on the footprint minus a
  margin (they floated over the brisis). Chimney stacks rise from the **eaves** (the roof record's height), so a
  stack anywhere on the footprint is grounded whatever the slope under it; they run in rows along the **party
  walls** (06_tiles' `party_walls`, one side of a shared wall only, now and then both), with a `pots` prototype
  (8 slots of 5-sided pots, `param` of them shown, fading at 500 m) on top. No parapets on roofed buildings
  (rise read from `uv2.y`). The building table comes from 06_tiles' own `prepared_buildings()`: a copy of its
  preparation drifted (zones, plant rooms on roofed buildings) and put items on the wrong roofs.

- **Ring and far air** (Berlin M7 fix round): `haze.height.edgeSky` turns the haze over `haze.edge`'s fade to the
  sky's colour in the view ray's own direction (the backdrop's rim seen from high up lies under the horizon: in the
  low-sky colour it bowed as an arc); a thicker day haze (`haze.height` density 1.1e-4, ramp 4000: about half at
  8 km near the ground) for aerial perspective over the city. Masses: `cellTint` (wall tints per mass and 400 m
  cell; one beige read as a single material) and `farWindows` (window contrast falling as windows near a pixel:
  dense dark window noise). Green layer: `lawnStyle.cover` opens the canopy noise to lawn where the cover map has
  grass (an open hill meadow drew as the noise's near-black understory); `ground.townLawn`, `townPaving`,
  `townNoiseGreen` (0: no noise-green blotches in the ring's block interiors).
  `ground.townMapNear` (0..1, default off; Tokyo 1): the ring's built-up land (calmTown) in the land cover map's own
  colour, its paving noise a +-15 % mottle over it, instead of the paving: with 06e_masses' `cover_roofs` the map's
  pale roofs and dark streets show from the ring's near edge, not only past its 5-9 km fade (Tokyo far-field fix).

## 11. Hills

Terrain from a DEM surface model with buildings/canopy removed (pipeline doc). Viewer side: facades measure height
from each building's base (`uv2`); trees/target/camera on `terrain.height`; hillsides without green become scrub
and woods; the far haze thins with height so ridges read against the sky; the backdrop's inner edge takes the
ground's exact heights (no crack). Rough edges left: mid-distance hills (6–8 km) read hazy olive, a colour seam where
the detailed ground area meets the backdrop, buildings on steep slopes partly buried (≈0.1 %).

## 12. Dusk and night (`night.js` + lit parts of every material)

**Architecture — lit copies swapped only after dusk:**
```js
u.withLights = (mat, emission) => { litCopy(mat).emissiveNode = (mat.emissiveNode ?? vec3(0)).add(emission.mul(u.lights)); return mat; };
function apply(root, on = state.on) { const swap = on ? litOf : dayOf; root.traverse((o) => { if (swap.has(o.material)) o.material = swap.get(o.material); }); }
```
`litCopy` copies the node slots and flags (`colorNode`, `normalNode`, `emissiveNode`, `positionNode`, `maskNode`,
`outputNode`, `receivedShadowPositionNode`, `side`, `transparent`, `depthWrite`, ...) and shares `userData`. Copies
are applied while `lights > 0` (sun below 6°). Reason: even a branch skipped by day on a uniform cost the facades
~10 % of their time; with copies daylight draws exactly the shaders it always did (verified: day frames differ from
before by ≤ 8/255 on 0.3 % of pixels). The night fog is a separate `fogNode` swapped the same way.

**Sky and light:** the Preetham sky goes dark within a degree or two of sunset, so a hand-tuned blue-hour sky is
added over it (sky material's lit copy, and the env copy so glass/water reflect it): zenith (0.04, 0.11, 0.38)·B,
horizon (0.3, 0.31, 0.38)·B with B = twilight × e^(0.3·elev), an orange glow over the set sun that narrows and
reddens as it sinks, the pink belt of Venus opposite, the city's warm glow on the haze (0.047, 0.04, 0.036) ·
lights. `lights = 1 − smoothstep(elev, −4°, 6°)`. Moon (a separate shadowless light, 0.09, (0.66, 0.74, 1)) takes
over below −2°. Exposure × (1 + 0.75 · (1 − smoothstep(elev, −10°, 0°))). Haze colour and hemisphere follow the
sky. Tree sky-light term dims with the hemisphere (crowns glowed green in the dark).

**Schedule of lit shares per kind and hour** (local time, linear between keys): offices 0.8 until 17 h then
0.66 → 0.34 (21 h) → 0.1 (24 h); homes peak ≈0.5 at 20–22 h; villages ≈0.56 at 21 h; shops 0.86 until 21 h then close
by 23 h; malls 0.8 until 21 h; feature lighting 17:00–23:00. Adapt to the city (office overtime, shop hours).

**Windows without the pixel mosaic** — the user: "the lighting is kinda pixelated, doesn't feel realistic" (at 2×):
- Rooms lit per zone: office zone 7 bays (staggered per floor by golden-ratio shifts), flat 2 windows, village room
  1, malls/factories/civic 4; on/off by hash against the floor's share; floor share scattered about the building's
  (offices **a floor at a time**: lit bands), building share = hour share × U(0.35, 1.45), 6 % vacant buildings.
- **Groups when small:** zones narrower than ~4 px or floors lower than ~3 px are lit in groups of 2, 4, 8… zones and
  1, 2, 4… floors, blended between group sizes like the glass variation, each group at its own share with a
  binomial-like spread `(h − 0.5) · 3.46 · sqrt(p(1−p)/n)` — towers fade into a soft, floor-banded glow at their mean.
- Lit windows give way to their mean **sooner** than the dark wall's windows (cells of ~9 → 3 px): under ~3 px a lit
  window beats with the pixel grid into stripes.
- The averaged colour is desaturated 35 % and dimmed to 0.32 (resolved warm windows clip to yellow-white; a saturated
  orange mean at low brightness reads as a **brown veil**) — **except in the water's mirror** (a uniform set when the
  rendering camera is below the sea), whose blur wants the true mean.
- Lamp colours: warm 2700 K (1, 0.6, 0.3), neutral (1, 0.8, 0.58), cool (0.74, 0.84, 1); homes ~85 % warm/neutral,
  villages more cool tubes, offices cool white; each building leans one way; 30 % of rooms outside curtain walls
  curtained (dimmer, warmer); home rooms a few bright, many dim; "off" rooms keep 2–6 % glow. Brightness: rooms 0.9, shops 1.1, signs
  1.5 (after 1.8/2.2 made "hard white strips at building bases"); signs of their own widths in 5 colours.
- Near details: sliding-window stiles, curtains drawn from the sides, a ceiling lamp's hot spot; curtain walls show
  the lit office through the glass (ceiling bright, blinds glowing).
- Rarer terms in `If` branches that whole buildings or bands skip (shops on the ground floor, street wash below
  30 m, feature lighting at tops, obstruction lights, roof lamps): ≈¼ of the lit shader off most pixels. Per-building
  values (share, zone width, colour mix) computed per vertex (`varying`).
- Supertall fins lit white brightening upwards with a glowing crown; a lit band on 20 % of towers > 120 m; **red
  obstruction lights > 150 m kept ~2 px across** (radius clamped 0.7–4 m) — a sub-pixel dot would vanish.
- Roofs: faint neutral warm-grey sky-glow bounce (0.012 × roof colour; at 3× that every flat roof turned brown), the
  odd warm lamp over a roof door (1 in 30 of 30 m cells), their mean once small.

**Streets:** lamp posts along both kerbs of every carriageway on the markings (10 m high, every 36 m facing on big
roads, 30 m staggered on small ones), sodium (1, 0.42, 0.1) on expressways and some districts' arterials (per 1.5 km
cell), LED elsewhere; pools average to their exact mean (`2h³/(P(d² + h²))`) as posts get closer than a few pixels,
plus the lamp heads' own glow once a road is a few pixels wide — from far above the network reads as glowing
lines. Runway edge/centre lights kept ~2 px. Yard lamps on only ~half the paved lots, pool size 8–30 m², their mean
when small (a regular grid read as **polka dots**); park lamps sparser; unmarked minor roads get scattered pools
(evenly lit they read as pale outlines round every block); sidewalks dimmer; floodlit aprons; junctions and bridge
decks at the streets' mean.

**A city without a lamp inventory (London M8):** `[lamps] generate` in 06e_lamps places posts along the OSM roads at
the country's spacing (UK: 28-33 m staggered on arterials at 8-10 m, 36 m one side on residential streets at 6 m),
coloured by who runs them (district areas, heritage kelvin in conservation areas, a share of whole streets on sodium),
gas lamps in a few circles, and special rows on named roads (the Embankment's dolphin lamps, on the water's side);
62k lamps for central London, Westminster's count within 10 % of the council's. Then the same `lamps.js` as an
inventory. Lessons from the night shots: the roof-door lamps read as a light pool on every roof from above
(`night.roofLamps: 0`); a boosted night mirror also boosts the lit haze over the horizon into a brown sheet over a
whole reach (boost only what is brighter than a knee, `water.night`), but at dusk the river must still mirror the
twilight (the night shares follow the city glow); per-landmark glows (`night.glows`) must be per pixel: per-vertex
bands interpolated across a triangle half inside the circle drew diagonal streaks down the tower.

**London M8 fix round (critic 6/10):** (1) *the far city an amber carpet*: the town ring's mean windows (masses.js,
orange at 16 % lit) plus a warm haze and hemisphere fill tinted every roof beyond 2 km. Found by switching terms
off one at a time over CDP (fog x0.3, hemisphere 0, city glow 0, town street glow 0: still amber; masses' emission 0:
gone). Fix: `night.masses` (mean x1, whitened, patchy per 50 m cell), `night.ambient` (night fill x0.35 and bluer,
haze navy). Aerial night photos: near-black roofs, light only from street grids and window points. (2) *a glow
circle lights everything in it*: the Eye's lavender circle (75 m) lit County Hall's wing as a translucent box and
every part of the wheel flat lavender; `hub`/`shell`/`plane` keep a glow to the rim, a second to the capsules (warm
white) and a third to the spokes. (3) *a flat glow on dark materials reads as nothing*: `flood` glows multiply the
albedo with a key light, so a slate roof needs k ~4 against stone's ~0.7. (4) *lamps vanish from the mirror*: the
mirror is drawn at half resolution, a 1.5-pixel head averages away; `lamps.mirror` grows the head and keeps its
energy times a gain (6; 25 smeared the river orange). (5) dusk needs its own fill (`duskFill`), not just a lighter
sky; and lamps reach full power long before the windows fill (`lampDusk`).

**The blue coat at dusk (every city; now the default `night.duskGrade`):** the twilight fill (`duskFill`, deep blue [0.45, 0.58, 1]) plus the
warm-dusk tint made the sky light ~0.4 and B/R 1.85 at the Dusk preset, and the night's exposure (x1.33, and x2 more
from the air with `highExposure`) brought it to about the day's shade: walls, roofs and streets one flat blue-slate
veil, windows and lamps no match. Measure the effective ambient as hemisphere intensity x exposure against the day's
(1.1 x 0.9), not the light alone. Blue-hour photos: the sky deep blue, the buildings it lights dim and only slightly
cool, the artificial light warm and showing. `night.duskGrade` (on by default; weighted to the twilight only, so day
and night stay pixel-identical): fill x0.4, twilight sky light x0.7, colour B/R ~1.27, highExposure half with depth.

**Still cool after the grade (London, Tokyo; opt-in `night.duskGrade.whole` and friends):** at London's Dusk (sun -7 deg) the roofs and unlit walls stayed one
navy slate (roofs linear B/R ~3.3, sRGB ~(4, 9, 13)): the grade had tinted only the twilight's share of the sky light,
the rest kept the city's blue night tint (`ambient.tint`), the moon (cool, from 48 deg up in the south-east) lit every
roof about as strongly as the whole sky, and nothing told west from east. Measured by switching each light off in the
page (hemisphere off: roofs to (1, 3, 4); moon off too: black; haze and sky: no change). Fix per city
(`duskGrade.whole`, `moon`, `afterglow`, `zenith`): the whole sky light near neutral, the moon a quarter, the western
afterglow as a soft directional light: roofs B/R ~1, walls facing the set sun lighter. Dusk lights are also a per-city
`dimDusk`: Singapore's [0.3, -11] left its CBD at 56 % of its windows at the Dusk preset (Hong Kong's [0.5, -8]: 80 %).

**An inventory without colour or flux (Berlin M8):** Berlin's open lighting inventory gives only the fixture type
(Ausleger, Aufsatz, Ansatz, Doppelausleger, Gas-Aufsatz/-Hänge...), so `[lamps] kinds` tables give each type its
height, kelvin, flux, `heads` and a `sodium` share of whole streets; gas mantles get their own green-gold (code 2).
Lessons: (1) a real inventory is denser than generated posts (19.6 m nearest-neighbour): London's pool 0.09 x2.4
lit Pariser Platz and Alexanderplatz like stages, 0.05 x1.4 reads as streets; (2) an inventory pulled for a box
three times the area cost the night overview 24 ms (1.46x day): `[lamps] clip` keeps lamps within 1.5 km of the
boundary (1.41x), the town ring beyond keeps the dim procedural lamps; (3) a lamp's pole quad is an additive line:
at street level a post beside the camera drew a wide yellow beam (`lamps.pole 0`); (4) a floodlit red-brick
bridge boosted in the night mirror smeared the river red (knee 0.08, bridges 0.5); (5) a glow on a building whose
own windows are lit (a glass-block tower in the lattice style) washes out pale instead of deep blue.

**Berlin M8 fix round (critic 6/10):** (1) *a glow circle lights what is round the landmark, not the landmark*: the Sony
Center's tent is the lattice material's fabric (kind 4), which no facade glow reaches, so its lavender landed on the
forum's roofs and the ring's walls while the tent stayed see-through; `night.glows` with `on: "lattice"` lights the
membrane (or a glass dome) itself, `radial` brightest at the mast. (2) *check which kind a regional style counts as at
night*: Berlin's own housing styles (altbau, platte, kma...) were not `residential`, so they took the civic schedule
and its cool lamps: homes dark with cold-blue windows. A style's `night: "home"` in its preset (was `night.homeStyles`). (3) *a small lattice-style building is a
lit glass hall*: under 30 m the lattice style glows white (the Louvre's pyramid), which made the Gedächtniskirche's
octagon a pale blob; `dark: [y0, y1]` puts out the buildings' own lights in a band, `grid` draws the glass blocks.
(4) *floodlight measured from each part's own foot* lit every figure on a roof (the Reichstag's towers, each
segment of the Fernsehturm's shaft) as a plinth: `flood.ground` measures from street level, `fallM` over metres,
`roof` leaves roofs dark, `low` leaves a mural wall to the night's light. (5) *the town ring darkened from the first
twilight* (its lit copy multiplied the walls by 0.55), a 2.4x step at the boundary at dusk: `masses.dusk` follows
the night's depth. (6) *a wine-red sheen on the river* was the mirrored horizon haze kept under the knee:
`water.night.desat`. (7) LED lamps by blackbody colour all read amber after tone mapping: `lamps.white` keeps the
LED/sodium/gas mix visible, `falloff` 3 and `spread` 1.1 make pools show in a dense inventory.

**A tropical city of public housing (Singapore M8):** (1) *the signature of an HDB town at night is its corridors*, not its
windows: the open corridor faces lit along every floor all night; `night.corridors` lights the `corridors` pattern's band
behind the parapet (a lamp every two bays, a few out, warm or cool per block), box-filtered to a band per floor and then an
even glow, so far slabs read as stacks of white lines beside the dotted window faces. (2) *the five-foot way went black
after dark*: its shop fronts are painted on the wall (no window box), so the shops' lights (glass-masked) never reached
them; `night.arcades` lights each shop front and the walkway's soffit by the shops' hour (Boat Quay's row along the river).
(3) LED cities: `ground.sodium` 0 everywhere including `motorway` (an orange expressway ring round a white city reads as
1990s), the town ring's posts warm and white LED (`townLights.led`), a grey sky glow and a navy zenith (the default warm
glow plus the far masses' amber windows made a brown carpet under a brown sky). (4) *figures take glows*: the Supertrees'
trunks (buildings glow) and canopies (`on: "lattice"`), the Flyer's rim/capsules/spokes (hub, shell, plane, as the London
Eye), the Helix (a plane along its chord, w covering its S-bend), ArtScience and the Merlion (`flood`). (5) a night shot
taken before the background warm-up ends shows every tower black (the lit copies not yet compiled): wait for `warmLeft()`
at night too.

**A white-LED megacity (Tokyo M8):** (1) *a brown sky over an amber city* is the defaults' sodium glow: navy zenith, a grey
glow (`skyGlow` [0.034, 0.036, 0.044]), `night.ambient`, white LED streets (`ground.sodium` 0.03-0.04, a third of the
expressways' cells sodium), the town ring's and the backdrop towns' lights white (`ground.townLights.white`, Singapore's
opt-in). (2) *office windows in seven-bay blocks read as a mosaic of rectangles*: `night.windows` with `zone` 2, `even`,
`litFloor` 0.94 lights offices a floor at a time in cool white, as Marunouchi and Nishi-Shinjuku look at 21:00; a cap
(`max` 0.65) keeps the lit floors under the landmarks. (3) *a landmark's glazed deck is a flat box under its feature
lighting*: a glow per glazed band with `grid` (mullions of 0.15-0.3 of a 2-2.4 m pane) and `dark` (the gold or Iki flood
off behind the glass) lights the windows; a lattice-style shaft under a `flood` glow shows its own steel pattern (the
Skytree's Iki) instead of a flat wash; split the shaft's glow round the decks or the decks take both. (4) *screens bloom*:
`facade.nightSigns` (screens 1, boards 1 instead of 4 and 2.2) keeps Shibuya's and Akihabara's colours under the bloom's
threshold. (5) the residential towers' oblique faces still tile (windows a pixel wide: the Singapore critic's mosaic):
`night.homes` (Singapore M8 fix round) is the fix.
**Singapore M8 fix round 1 (the critic's "camouflage"):** (1) *a day-time grid fade must not decide the night's windows*: the
city's `facade.farFade` (the window grid faded to its mean from ~25 px a bay, against black speckle by day) also set where the
lit windows became their cell's mean, so from 300 m every cell was a solid tile in its room's tone with no wall between;
`night.homes.far` gives the lights their own fade (from ~5 px a bay to ~2), and `room`/`curtains` make lit rooms bright and
alike (lo..hi evenly, few curtains) rather than many dim mid-tone rooms: dark walls with discrete lit windows. (2) *container
terminals are white, not orange*: the aeroway layer's sodium share and its 120 m zone noise read as orange clouds from the
air (`ground.apronLights`). (3) a park's paths and a promenade lit like a road (10 m lamps, 15 m apart) are one even pale
band; 3.5 m lamps 26 m apart give pools (`ground.plazaLamps`). (4) the Supertrees: one glow over the grove makes one colour
and a glow's hard circle cuts any canopy it half covers: one lattice glow per tree (its canopy's circle and height), lines
lit (`members` > 1) over dim panes, the trunks' glow kept low (`fade` 0, the bottom 18-26 m). (5) the far HDB towns read as
lit towers only with whiter lamps and a corridor band per storey on half of them (`night.masses.lamp`, `.corridors`).

**A dense, late-lit city (Hong Kong M8):** (1) *a home schedule at the default 0.5 (Shenzhen's) is a dark city here*: Hong Kong's flats are
mostly lit at 20-22 h (0.72 at 21 h), offices late (0.6 at 21 h), shops to 22-23 h; with the lit share up, the lit windows'
mean on 2-3 km slopes turned into a blotchy mosaic of tan blocks: groups of rooms each at their own share
(`night.homes.spread` 0.35 narrows it), on top of Singapore's `night.homes` (bright, even rooms; their own far fade).
(2) *street signs need their light on the street*: matte boards with no spill read as stickers; `rooftopLook.signSpill` lays
an additive pool per lit board on the ground (its colour, area x height / distance^3), with `signsGlow` 1.6 for the
boards (kept under the bloom's white). (3) *a junction lit at the streets' mean is a flat polygon*: under sodium an orange
blob, under LED a grey one, darker than the pooled lanes beside it (`ground.junctionPools`: pools on a jittered grid, k
1.7). (4) *a glow ball that changes colour from frame to frame* is a huge but finite pixel (the bright pass already
dropped NaN/Inf), blurred through the bloom's mip chain: `glow.max` caps the bright pass. (5) LED city: sodium only on
a few arterial cells and a third of the expressways; navy zenith over a grey glow, as Singapore.

**Air:** after dark the fog adds haze lit from below by the city: thickest low, thinning over 100 m of height,
optical depth `0.8e-4/m` at ground level integrated in closed form along each sight line (per vertex), **left out
over the first km** (0.8–4 km fade) — nearby it only greyed the blacks. The mirror camera uses its height above
the water plane (at −440 m the `exp(−h/100)` term was ~80× and drowned the mirrored city: "the bay lost its
reflections").

**Cars:** headlights (white ×5) and tail lights (red ×3) on moving cars; far boxes' whole front/rear faces ×8/×6 so
a far car stays a white or red point; parked cars dark. **Water:** mirrored lights stretch into longer, brighter
streaks (tap spread × (1 + lights), brightness × (1 + 0.6 lights)).

**Glow:** bloom only while lights are on: strength 0.45 × lights, radius 0.6, threshold 0.7; see
`performance-and-loading.md` for the pipeline set-up.

**Measuring "veil" objectively:** luminance percentiles (10/25/50/95/99) and the mean RGB of the 15th–40th
percentile pixels ("dark mid-tones") of a standard view, before vs after; roofs' bounce moved dark mid-tones from
(5.7, 5.6, 7.8) to (13, 9.4, 5.5) — brown — until reduced.

## 13. Feedback → fix index

| User feedback | Fix (section) |
|---|---|
| "buildings interconnected" / "cuts some buildings into more parts" | footprint source choice per building (pipeline doc) |
| "I don't see roads" | roads, bridges, markings (5) |
| "glass looks weird light blue" / "light blue blocks from far" | city probe, coated glass, surviving variation (3) |
| "toooo glassy" / "50 is a good default" | capped Fresnel, dimmed sky, soft shoulder; slider 0.5 (3) |
| "trees and water are colour blobs", "ponds should look like water" | leaf-card trees + impostors (8); wave slopes, colours, mirror (6) |
| "buildings on the road" | clearance rule in the pipeline |
| "yellow-green grass", "mangrove area" | cooler lawn, mud layer (4) |
| "water has no movement, it should be flowing" | drifting scales, flow maps, throttled loop (6, viewer doc) |
| "white traffic lines not in the right positions" | half-lane offset bug (5) |
| "hills, rooftop clutter, cars, night mode" | 9–12 |
| "lighting is pixelated" | grouped rooms, sooner averaging, sparser lamps, glowing haze (12) |
| (after the fix) bay lost reflections, brown veil | mirror camera height, no clip dimming in the mirror, weaker roof bounce (12) |
