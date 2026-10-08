# build-3d-city

An agent skill and a city engine for building a real city in 3D in the browser from open data: every building with
its real footprint and height, terrain and hills, roads with markings, water that moves and mirrors, trees, rooftop
clutter, traffic, landmarks modelled after photos, day, dusk and night — in a page that loads in seconds and draws
nothing while nobody touches it.

You don't run it by hand. You ask your coding agent ("build Lisbon in 3D"), and the skill tells it how: scope the
city with you, fetch and clean the data, build it milestone by milestone, and have an independent critic agent judge
each milestone against real photos until it looks right and stays fast.

- **Pipeline:** Python, run with [uv](https://docs.astral.sh/uv/) (`engine/pipeline/`, package `city3d`). OSM,
  official building datasets, LiDAR and global DEMs in; packed, streamed tiles out.
- **Viewer:** [three.js](https://threejs.org/) WebGPU with TSL node materials and a WebGL 2 fallback
  (`engine/viewer/`): static files, no build step.
- **A city is configuration:** a `city.toml` for the pipeline and a `city.json` for the viewer.

## What it can do

The live demo, seven cities built with this skill: **https://slopcity.rzheng.top/** — for example Tokyo (49 km², 100k
buildings, Mount Fuji on the horizon), Hong Kong (both harbour shores and the Peak, from official LiDAR), New York
(Manhattan with Brooklyn's and New Jersey's waterfronts), Paris, London, Berlin and Singapore. Each loads to
a usable view in about 5–7 s and has a menu of places, a time-of-day slider and switches for every layer.

## Requirements

- An AI coding agent that loads skills: Claude Code or Codex (others that read `SKILL.md` folders should work).
- A machine with a GPU (an integrated laptop GPU is enough; the reference builds were made on an Intel Iris Xe) and
  **16 GB of memory or more**: a city loaded in Chrome takes 4–5 GB, and a pipeline stage several GB.
- Google Chrome (WebGPU; the agent drives it over the DevTools protocol for screenshots and measurements).
- [uv](https://docs.astral.sh/uv/) (Python), Node.js 22+, and tens of GB of free disk for a big city's data.
- Optional: Docker, for a local Overpass server (big cities hit the public servers' rate limits), and ffmpeg for
  fly-through videos.

## Install

Put this folder where your agent looks for skills, in your project or your home directory:

```sh
# Claude Code
git clone <this repo> .claude/skills/build-3d-city
# Codex (and a shared location other agents read)
git clone <this repo> .agents/skills/build-3d-city
```

One copy can serve both: clone into `.agents/skills/` and link `.claude/skills` to it.

## Quick start

Open your agent in an empty project folder and ask:

> build Lisbon in 3D

What happens next:

1. **Phase 0, with you.** The agent researches the city (districts, area, building counts, landmarks, terrain) and
   shows you a map with 2–4 boundary options and their sizes. You pick one. This is the one decision that is always
   yours.
2. **Milestones, on its own.** Data (M1), the building table (M2), terrain, roads and water with a first viewer (M3),
   then facades and landmarks, ground, trees and cars, hills, night, loading speed, and the menu (M4–M10). It starts
   from the nearest example city in `examples/` and checks in briefly after each milestone with screenshots and
   numbers.
3. **A critic per milestone.** A fresh agent that didn't build it compares screenshots with real photos and the
   performance budget, and scores it; two rounds, then remaining issues are written down, not hidden.
4. **Your review.** Look at the result, send notes with screenshots; the agent fixes each at your camera angle.

It asks you only for what is genuinely yours: the boundary, licences or accounts, big downloads, and taste questions
the evidence can't settle.

## Project layout

The skill recommends (and its docs assume) this layout; another root works:

```
<project>/
  .claude/skills/build-3d-city/   this skill (or .agents/skills/)
  demos/<city>/                   tracked: city.toml, pyproject.toml, README.md, REPORT.md,
                                  checks/, data/, scripts/, generated/, eval/ (ignored), web/
  demos/data/<city>/              git-ignored: raw downloads and everything the pipeline writes
```

Serve `demos/<city>/web/` as static files to view a city.

## What's in this folder

- `SKILL.md` — the entry point the agent reads: rules, phases, milestones, the critique loop.
- `references/` — the depth: data sources, pipeline, facades, materials, performance, testing, critique, running a
  build (several cities, agents, memory, merging, publishing), fly-through videos.
- `engine/` — the pipeline and the viewer, each with a README of every setting.
- `examples/` — configurations of seven reference cities to start from.
- `scripts/` — Chrome automation, the speed test, pixel diffs, machine locks, local Overpass.

## Data licences: credit your sources

Every city is built from other people's data, and you must credit it wherever you show the result:
OpenStreetMap (ODbL: "© OpenStreetMap contributors"; databases derived from it are share-alike), Copernicus DEM,
national and city open data (often CC BY or an open government licence), and some sources that are
**non-commercial only** (flagged in `references/data-sources.md`). The skill records every dataset's licence in the
city's README and in the viewer's About panel; read them before publishing.

## Limits, honestly

- **A GPU machine and memory.** 16 GB is workable with discipline (one city in Chrome at a time); 8 GB is not.
- **Hours per city.** A small core takes a few hours; a big city through all ten milestones took the reference builds
  one to three days of agent time.
- **Usage costs.** Many agent-hours per city. Running five or more agents in parallel exhausted a weekly usage limit
  in two days; the skill caps parallel agents at about three.
- **Plausible, not surveyed.** Footprints, heights, roads and terrain are real where open data has them; facades,
  trees, cars and rooftop clutter are invented to look right. Data-poor regions look worse.
- Tested mainly on Linux with Chrome; other platforms should work but have seen less use.

## Licence

MIT — see [LICENSE](LICENSE). This covers the skill, its docs and the engine's code. The three.js copy vendored in
`engine/viewer/vendor/` is MIT too (its notice is beside it). City data you download and the cities you build from it
carry their sources' licences (OSM's ODbL and others), which you must follow and credit.
