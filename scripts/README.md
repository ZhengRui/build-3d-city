# Scripts

Helpers for building, measuring and guarding a city. Node 22+ (no npm packages), bash, Docker for the local
Overpass. Each script's header comment is its full manual (`node <script> --help` prints it for the `.mjs` ones).

| Script | What it is for |
|---|---|
| `cdp.mjs` | Drive a private Chrome over its DevTools port: navigate, evaluate JS, screenshot, console, CPU profile. For agents without a browser MCP, or with one shared by others. `CDP_PORT` (default 9333). |
| `speedtest.mjs` | One speed test for every city after a viewer change: load time, settled frame ms, orbit and drag fps, idle frames, against a saved baseline. Starts its own server and GPU Chrome per city. |
| `pixdiff.mjs` | Reference screenshots of every city (day, night, dusk; WebGPU or WebGL 2) and a pixel diff against them: proof that a change kept, or changed only where intended, the picture. `--params` A/Bs a viewer switch in one tree. |
| `facade-ref.sh` | Take the reference set for `pixdiff.mjs` (all cities' standard views, both backends, a repeat for the noise floor) before a refactor. |
| `local-overpass.sh` | Build a local Overpass API in Docker from a BBBike extract when the public servers refuse a big city's queries. |
| `lock.sh` | Machine-wide `chrome` and `pipeline` locks so parallel agents never load two cities in Chrome or run two heavy stages at once. `speedtest.mjs` and `pixdiff.mjs` use it. |

## Where they read and write

Defaults assume the skill sits at `<project>/.agents/skills/build-3d-city/`, cities at `<project>/demos/<city>/`
and their data at `<project>/demos/data/<city>/`. `<project>` is found as the folder four levels above `scripts/`;
when that folder is a git worktree, its main tree, so all worktrees share one data folder and one set of locks.
Override with environment variables:

| Variable | Default | Used by |
|---|---|---|
| `CITY3D_PROJECT` | four folders above `scripts/` (a worktree: its main tree) | all |
| `CITY3D_DATA` | `<project>/demos/data` | all |
| `CITY3D_LOCKS` | `<data>/.locks` | `lock.sh`, `speedtest.mjs`, `pixdiff.mjs` |
| `CITY3D_TREE` | four folders above `scripts/` (the tree whose viewer is served) | `speedtest.mjs`, `pixdiff.mjs` |
| `CITY3D_DEMOS` | `<tree>/demos` (holds `<city>/web/`) | `speedtest.mjs`, `pixdiff.mjs` |
| `CITY3D_VIEWS` / `--views-file` | none: the built-in table of the reference project's cities | `speedtest.mjs`, `pixdiff.mjs`, `facade-ref.sh` |
| `CHROME_BIN` | `/opt/google/chrome/google-chrome` (with `--wayland`) | `speedtest.mjs`, `pixdiff.mjs` |
| `CITY3D_DISPLAY`, `CITY3D_XAUTHORITY`, `CITY3D_CHROME_GROUP`, `CITY3D_CHROME_EXE` | `:0`, `/run/user/<uid>/gdm/Xauthority`, `render` (`""`: no `sg`), `/opt/google/chrome/chrome` | the X11 Chrome launch of `speedtest.mjs`, `pixdiff.mjs` |
| `OVERPASS_DATA` | `<data>/overpass` | `local-overpass.sh` |
| `FACADE_REF_OUT`, `REPEAT_CITY`, `REPEAT_VIEWS` | `<data>/facade-ref`, `paris`, two Paris views | `facade-ref.sh` |
| `PORT`, `CDP` | 8795, 9355 | `facade-ref.sh` (also `--port`, `--cdp-port` on the `.mjs` scripts) |

Your own cities' standard views, for `speedtest.mjs` and `pixdiff.mjs` (names from each `city.json`'s `views`):

```json
{ "lisbon": ["Lisbon overview", "Rua Augusta (street level)", "Baixa", "Belém Tower"] }
```

`speedtest.mjs` takes the first three as overview, street level (measured animated) and dense area; `pixdiff.mjs`
shoots all four. With a views file and no `--cities`, both run the file's cities.

## Rules built into the Chrome scripts

`speedtest.mjs` and `pixdiff.mjs` wait while the pipeline lock is held, take the chrome lock with the real browser
PID, start Chrome with a fresh profile under `<data>/.chrome/` and delete it on close, check at least 4 GB of
available memory before every load and abort a city under 1.5 GB, and never `pkill`. A city in Chrome takes 4-5 GB.
Keep screenshots and profiles on disk: `/tmp` is RAM on many Linux systems.
