---
name: build-3d-city
description: Build a realistic, browser-responsive three.js (WebGPU/TSL) 3D reconstruction of a real city or part of one from open data — boundary scoping with the user, data download and cleaning, building footprints and heights, terrain, roads, water, facades and photo-referenced landmarks, trees, rooftops, cars, waves, night mode, streaming and performance — in an agentic loop where an independent critic reviews every milestone until it looks real and stays fast. Use when asked to build, map or reconstruct a 3D city, districts, or a city scene from OSM / open building data (e.g. "build Lisbon in 3D", "do the centre of Seoul like the Tokyo example").
---

# build-3d-city

Turn a city name into an interactive, photoreal-in-spirit 3D city in the browser: every building from open data
with its real footprint and height, procedural facades that read right from 30 m to 30 km, landmarks after photos,
terrain, roads with markings, water that moves and mirrors, trees, rooftop clutter, traffic, day and night, and a
page that loads in seconds and draws nothing while nobody touches it.

The skill is an **engine plus a method**. The data pipeline is `engine/pipeline/` (Python package `city3d`, run with
`uv`; its README has the CLI and every setting) and the viewer is `engine/viewer/` (three.js WebGPU/TSL modules with
a WebGL 2 fallback; its README has the module map and every key). A new city is configuration, not a copy of code:
a `city.toml` (districts, CRS, sources, margins, views, summits, a region preset for styles, species, cars and
roofs) and a `web/city.json` (title, About, sun, time presets, features, look). Add a source adapter or a region
preset to the engine where the city needs one; don't rewrite what already works.

The method was worked out on **eight reference builds** (Shenzhen, New York, Paris, London, Berlin, Singapore, Hong
Kong, Tokyo); you have none of their data, but seven of them (all but Shenzhen, the first) have their
configurations in `examples/<city>/`, and the lessons of all eight, with numbers, are in `references/`.
**Start a new city from the nearest example of the same type** (tower city, European block city, inland or
coastal, left- or right-hand traffic) and go through `references/porting-checklist.md`.

"Photoreal" here means *plausible and consistent*, not surveyed: real geometry where open data has it, invented but
believable detail (facades, trees, cars, rooftop clutter, markings) where it doesn't. Say in the viewer's About
text what is real and what is invented.

## Project layout (recommended default)

Paths in this skill are relative to the project root, the folder that holds `demos/`. Another root or folder
naming works; keep the split between small tracked code and large ignored data.

```
<project>/demos/<city>/            tracked, small
  city.toml  pyproject.toml        the pipeline's config; a three-line pyproject (engine README)
  README.md                        scope and boundary, stages, real vs invented, licences, sources tried and dropped
  REPORT.md                        the build log: milestone entries, critic rounds, Known issues, "For M<n>"
  checks/                          pipeline check reports (*.md; *.png committed only at a milestone's end)
  data/                            landmark research (landmarks*.csv, landmark_facades.*)
  scripts/                         city-only scripts, named m<N><x>_<what>.py (e.g. m4f_seat_check.py)
  generated/                       TOML that scripts write (e.g. structures-<name>.toml), `include`d by city.toml
  eval/                            screenshots and measurement output: git-ignored, only notes committed
  web/                             city.json + tracked links index.html, engine -> the skill's engine/viewer,
                                   git-ignored data links (tiles, blocks, markings, trees, shores, cars, rooftops, lamps)
<project>/demos/data/<city>/       git-ignored, large: raw/ downloads (each with a README.txt: source, licence,
                                   vintage), pipeline outputs, served tiles
```

`web/` alone can be served as static files.

## Hard rules

1. **Boundary first, with the user.** Before any download, propose districts and agree the boundary (Phase 0). It is
   the one decision that is always the user's.
2. **Then run on your own.** After the boundary, work through the milestones without asking; ask only for what is
   genuinely the user's call ("When to ask").
3. **Every milestone passes an independent critique** (`references/critique.md`): a fresh subagent that did not
   build it judges screenshots against reference photos and the budget. **Default two critic rounds.** If one
   high finding is left after round 2, do one narrow fix (no new critic) and close; everything else goes to the
   REPORT's Known issues (milestone, view, what, fix idea, severity) and the run moves on.
4. **Idle draws nothing.** Render on demand; animation (waves, traffic) only while in view, throttled, and stopped
   after a few minutes without input. Performance is a feature (a laptop overheated once), measured every milestone.
5. **Daytime cost never pays for extras.** Night, glow etc. live in material copies/passes swapped in only when
   needed; measure before/after.
6. **Shared engine changes are opt-in.** A new engine feature is off by default and switched on in the city's
   config. A default change (or a bug fix that changes pixels) needs a pixel diff of every finished city — day,
   dusk and night, WebGPU and WebGL 2 — against the last *approved or published* build (not just the previous
   tree), plus the speed test; list the intended pixel changes for the user to overrule. Gate a city-only shader
   path on an explicit config key, never on a data range: a roof path gated on `uvRange.base[1] > 0` leaked into
   tiles packed before roof codes existed (New York), and a later "keep New York pixel-identical" check froze the
   regression because it compared against the regressed tree.
7. **Data never in git.** Code in `demos/<city>/`, data in `demos/data/<city>/`, viewer data reached through
   git-ignored links in `web/`. Keep the history light: check images only at a milestone's end
   (`git restore demos/<city>/checks/*.png` after interim runs); script-made settings in `generated/` files,
   committed when they really change; screenshots stay in `eval/`, ignored.
8. **Commit locally, never push** unless the user asks. Small logical commits whose messages say what and why, with
   numbers. Never commit on the default branch; prefer linear history (`references/running-a-build.md`).
9. **Don't touch the user's things.** Their preview server, ports, browser tabs, data folders others serve: read
   only. Test servers on your own port, killed by the PID you recorded, never by pattern.
10. **Mind the machine.** A city loaded in Chrome takes **4–5 GB** (a bare Chrome ~1.8 GB); a heavy pipeline stage
    several GB. Across all agents: **one Chrome with a city loaded and one heavy stage at a time**, started only with
    ≥ 4 GB available, guarded by `scripts/lock.sh`. Restart Chrome with a fresh profile after two full-city views
    (GPU memory creeps). `/tmp` and agent scratch may be RAM (tmpfs): keep shots, profiles and big files on disk.
    Linux's systemd-oomd kills the whole terminal session, every agent with it, under sustained pressure.
11. **Parallelise when it doesn't cost quality** — research, separate layers, the critic — but **cap at ~3
    builder/critic agents at once**: five or more in parallel used up a weekly usage limit in two days. Use a cheaper
    model tier for well-specified volume work (downloads, measurement, docs) and the builder's tier for judgment and
    every critic. Cross-cutting changes (terrain, a data format, the render loop) wait until parallel work merges.
12. **Licences recorded** for every dataset (README "Licences"), non-commercial ones flagged; credit the sources
    wherever the city is shown.
13. **Verify in a browser before claiming anything looks right** — screenshots, console errors, fps, and both WebGL 2
    and WebGPU when a change touches shaders (`references/testing-and-tooling.md`). Look at every shot yourself
    before a critic or the user does.

## Phase 0 — scope the city with the user

Goal: a boundary the user agrees to, sized so the result stays fast.

1. Look the city up: admin hierarchy in OSM (`relation["boundary"="administrative"]`; levels differ per country —
   check, don't assume), area in km², rough building count (Overpass `count` or the footprint dataset), the famous
   landmarks, the terrain and water.
2. Size it against the reference builds (dense cores have far more floor area per km²: scale the area down):

   | Example | Area (land) | Buildings | Building triangles | First load | Usable view (WebGPU) |
   |---|---|---|---|---|---|
   | Shenzhen (3 districts) | ≈ 660 km² | ≈ 0.21 M | 3.7 M | ≈ 60–66 MB | 4.9 s; 10–12 s at 80 Mbit/s |
   | Tokyo (10 central wards) | 49 km² | 100 k pieces | 2.0 M | 40–47 MB | 6.4 s |
   | Hong Kong (both harbour shores) | 135 km² | ≈ 40 k | — | 46 MB | 6.6 s |
   | Singapore (centre, 500 m band, 16 k far blocks) | — | — | — | 12–14 MB | 5.3 s |

   Usable-view times are unthrottled on a slow integrated GPU (Intel Iris Xe) at 1600 × 1000, dpr 2.

3. Propose 2–4 options — e.g. *core* (the postcard: CBD, waterfront, main landmarks), *core+* (the next ring),
   *whole city* (with an honest size/perf estimate) — each with districts, area, estimated buildings/tiles/MB, and
   which landmarks and scenery it includes. Recommend one.
4. **The edges, both ways.** A wide ring of ordinary town slows every stage (Paris, London and Berlin each took in
   more than the postcard needed): propose a tight core first and say what each ring buys. But in a tower or flat
   megacity an empty plain beyond the core reads as countryside from high views, and a painted roofscape alone does
   not fix it. Offer the cheap middle way: tall buildings beyond the detailed area as simple blocks
   (`masses_tall_within`, `masses_ring`; Singapore: 16 k blocks, +1 MB) so the skyline reaches the horizon.
5. Settle the margins (Shenzhen: roads 1 km outside, ground 4 km, far terrain backdrop to ~36 km; Tokyo's backdrop
   reached Mount Fuji, 98 km) and any must-have landmarks or views.
6. **Show the options on a map**: a page with a real basemap (Leaflet or MapLibre with OSM tiles) showing each
   option's polygon in its own colour with name, km², buildings and MB in a legend, landmarks as pins, water and
   hills, the margins as dashed rings; toggles per option and ring. The user may never have been to the city.
7. Record the decision in `demos/<city>/README.md` and `city.toml` (`[districts]`, or a clip GeoJSON).

## Setup

- `demos/<city>/` from the nearest `examples/<city>/` (its `city.toml`, `web/city.json`, `pyproject.toml`), then
  `references/porting-checklist.md` line by line (CRS, districts, sun latitude, regional datasets, driving side,
  styles, species, car mix, rooftop types, coast vs inland). Create `demos/data/<city>/raw/`.
- `web/`: `city.json` (every key in `engine/viewer/README.md`), tracked relative links `index.html` and `engine` to
  the skill's `engine/viewer/`, and the data links the pipeline's `link_web` makes. Serve that folder.
- Data sources for the region: `references/data-sources.md` (official LoD1/LoD2 data beats global datasets wherever
  it exists). For a big city, a **local Overpass** (`scripts/local-overpass.sh`, Docker) saves hours of 429/504s.
- `uv run city3d all` in the city folder runs the pipeline (`city3d <stage>` one stage, `city3d stale` after a single
  stage, `city3d verify` before a critique). The viewer is static files (three.js from a pinned CDN import map, or
  vendored).
- Two traps the engine handles: an **inland city** (`coast = false` or `"auto"`) gets the whole area as land and a
  ground lowered to its lowest point; `city3d all` runs `08_trees --green-only` before `05a_terrain` (the terrain
  uses its green cache) and `08_trees` after it.

## Milestones

Each milestone: build → its checks → screenshots from the standard views (`references/critique.md`) → critique loop
→ an entry in `REPORT.md` → a short checkpoint to the user (what changed, 2–4 shots, numbers, what's next). Don't wait
for a reply unless you asked a question. Independent milestones may be built in parallel and judged by one critic
(M4 landmarks ∥ M4 facades; M5 ∥ M6), scoring each.

| # | Milestone | Done when | Main references |
|---|---|---|---|
| M1 | Data in hand: boundary, OSM, footprints, heights, DEM | coverage and alignment report in `checks/` | data-sources, data-pipeline |
| M2 | Building table: one footprint per building, best height, kinds | `checks/buildings.md` + `quality.md` clean: no blobs extruded as walls, no underground stations, landmarks at listed heights | data-pipeline, buildings-and-landmarks |
| M3 | Terrain, ground, roads, bridges, water; tiles; first viewer | loads, nothing floats/sinks, coast meets sea, no roads through buildings | data-pipeline, viewer-architecture |
| M4 | Facades (nearest regional preset + `facade-catalogue.md`) and landmarks after photos | towers read as the real ones; no "light blue blocks", not "too glassy" | facade-catalogue, buildings-and-landmarks, materials-and-realism |
| M5 | Ground realism: paving, parks, markings, shores, moving water | no colour blobs; lane lines; water moves only while visible | materials-and-realism |
| M6 | Trees, rooftop clutter, cars/traffic | near and far convincing, draws within budget | materials-and-realism, performance-and-loading |
| M7 | Hills, far backdrop, the edges | real hills at their place and height, seamless edges, no empty plain | data-pipeline (terrain) |
| M8 | Dusk and night | lit windows without mosaic, street light, glow, reflections; dusk no darker than night; day unchanged | materials-and-realism (night), critique (night checks) |
| M9 | Loading and responsiveness, on a quiet machine | usable ≲ 10–15 s on a home connection, no main-thread stall > ~350 ms, no flicker on changes of light | performance-and-loading |
| M10 | Menu, places, polish, README, licences | place groups Areas / Street level / Landmarks / Horizons / Night, each checked by eye; a switch per optional layer; About honest | viewer-architecture |

M1–M3 first; terrain can come earlier in a hilly city; M9's budget is checked at every milestone. M9 needs a quiet
machine: if memory pressure or other agents skew it, record the numbers as a Known issue, not as "passed". After M10
come the **user-review round** and **publishing** (`references/running-a-build.md`).

## The critique loop

`references/critique.md` has the brief, rubric, evidence list, night checks and pass bar. In short:

- The critic is a **fresh subagent** (never the builder, no access to its reasoning or the last critic's text), given
  the milestone's goal, screenshots (standard + milestone views, before/after), the numbers, and the rubric. It finds
  its own reference photos and returns scored findings, worst first, with view and fix idea.
- **The user's items are checked at the user's camera.** Pass the user's words and camera; the critic re-shoots there
  and from four sides and rules each item fixed / half-fixed / not fixed. Half-fixed is a high finding. "Centred on the
  outline" is not evidence; a picture from where the user stood is.
- The builder fixes the top findings (visual gain per cost, never trading away speed), re-shoots the same views, and
  calls a *new* critic. Two rounds by default (hard rule 3).
- The user's feedback outranks the critic's; both become lessons (REPORT, commit messages, and this skill's
  references when general).

## When to ask the user

Ask (short, with a recommended option) only for: the boundary and margins (always) or a later scope change; a dataset
that needs an account, a licence acceptance, a paid tier or a download over a few GB; taste the evidence can't decide
(show both); anything that changes the user's files, servers or published pages; a trade-off that costs the user
something noticeable (download +25 %, slower load); an engine default change (hard rule 6). Batch questions in one
message. Otherwise decide, say so in the checkpoint, and keep going.

## Running the build

One city in one session works; several cities go faster with a controller session that delegates to subagents. Both,
plus briefs, worktrees, merging, the lock script, the REPORT convention, the user-review round and publishing:
`references/running-a-build.md`.

## References

| File | What's in it |
|---|---|
| `references/running-a-build.md` | one city or several with a controller; brief template; concurrency and usage limits; memory and locks; worktrees and merging; hand-back; REPORT and Known issues; user review; publishing |
| `references/data-sources.md` | datasets used/evaluated, licences, what to use per region, local Overpass |
| `references/data-pipeline.md` | every pipeline stage: algorithms, parameters, formats, run order, runtimes |
| `references/buildings-and-landmarks.md` | footprint/height quality, facade style assignment, landmark photo research |
| `references/porting-checklist.md` | everything to set for a new city, starting from the nearest example |
| `references/facade-catalogue.md` | every facade feature and pattern, the presets and their base chain, mapping a city's building types |
| `references/viewer-architecture.md` | renderer, on-demand loop, controls, menu, modules, test handles |
| `references/materials-and-realism.md` | how each layer was made realistic and the feedback that drove it (incl. night) |
| `references/performance-and-loading.md` | budgets, culling/LOD, streaming, shader compilation without stalls |
| `references/tsl-and-three-pitfalls.md` | concrete three.js/TSL gotchas and their fixes |
| `references/testing-and-tooling.md` | browser testing (WebGL 2/WebGPU, dpr 2), CDP script, speed test, pixel diff, profiling |
| `references/critique.md` | critic brief, rubric, standard views, night checks, user items, pass bar |
| `references/flythrough-video.md` | a cinematic fly-through video rendered frame by frame (`__viewer.film`), route design rules |
| `examples/<city>/`, `examples/README.md` | the configurations of seven reference builds (`city.toml`, `city.json`, city scripts, generated structures), a table by city type, and how to start a new city from the nearest |
| `engine/pipeline/` | the data pipeline (`city3d`): stages, source adapters, region presets, `city3d verify`; README = CLI + city.toml reference |
| `engine/viewer/` | the viewer, configured per city by `web/city.json`; README = module map + every key |
| `scripts/cdp.mjs` | drive a standalone Chrome over its debugging port: navigate, eval, screenshot, profile |
| `scripts/speedtest.mjs` | speed test for every city after every viewer change: load, settled, moving, animating, idle; JSON per run and a table against a saved baseline |
| `scripts/pixdiff.mjs` | reference shots of every city (day, night, `--times dusk`; WebGPU or `--webgl`) and a pixel diff against them; `--params 'a=1&b=0'` for an A/B of viewer switches in one tree; `--shader` for the facade shader's size |
| `scripts/lock.sh` | machine-wide locks (`take`/`pid`/`release`/`show` for `chrome` and `pipeline`) shared by agents and the test scripts |
| `scripts/local-overpass.sh` | a local Overpass API in Docker from a city extract (one import at a time, ≥ 6 GB free) |
| `scripts/facade-ref.sh` | the pixdiff reference set (all views, both backends, a noise-floor repeat) taken before a viewer refactor that must not change the picture |
| `scripts/README.md` | every helper script, its environment variables (`CITY3D_PROJECT`, `CITY3D_DATA`, `CITY3D_LOCKS`, `CITY3D_VIEWS`) and the views-file format (`--views-file` for your own cities) |

Read a reference when you reach the milestone that needs it, not all up front.
