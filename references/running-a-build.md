# Running a build

How a city build is organised: who does what, how agents share one machine, how work lands in git, what gets
written down, and how the result reaches the user and the web. Distilled from eight reference builds (the first
five one or two at a time, the last three — Singapore, Hong Kong and Tokyo — in parallel under a controller, M1 to
M10 in about three days on one 15 GB laptop).

## 1. One city or several

**One city, one session.** The session builds, spawns a fresh critic subagent per milestone round, and uses
subagents for parallel research or independent layers. Enough for a first city or a small scope.

**Several cities: a controller.** A controller session plans, delegates, guards the machine and owns the truth; it
builds nothing itself except glue (a config line, a merge, a commit, a REPORT entry). It:

1. reads the skill (SKILL.md, the porting checklist, the critique brief, the relevant data-source rows) and the
   Phase 0 decisions;
2. delegates every milestone to subagents, as many in parallel as memory, the locks and the usage cap allow (§3);
3. owns the machine: memory, disk, ports, Chrome instances, locks, orphan processes; after each agent returns it
   checks `free -g`, `df -h`, `scripts/lock.sh show`, and kills orphans it can attribute;
4. owns each city's `REPORT.md` and its Known issues (§7);
5. commits, checkpoints, and keeps a **decisions file** for the user (§8).

Order that worked for three cities at once:
- **M1 for all cities together** (research, downloads, adapters, `city.toml`: mostly light work), heavy stages behind
  the pipeline lock.
- **Then M2–M3 one city at a time, simplest first.** Singapore (OSM plus official storeys, flat, global DEM) went first
  and shook out what all three shared (left-hand traffic, tropical ground, tower-city settings); Hong Kong (official
  buildings, LiDAR on steep slopes) next; Tokyo (a new CityGML adapter, started in M1 in its own worktree) last. Later
  cities started their M2 early in their own worktrees whenever the machine had room.
- From M4 on, milestones of different cities ran side by side, and independent milestones of one city too
  (landmarks ∥ facades, ground ∥ trees/cars).

**Time boxes** keep a run moving: M1 ~2 h per city (a new source adapter ~3 h in parallel), M2 ~2 h, M3 2–3 h. When
a box runs out, record the state and move on, unless the city is broken (nothing loads, a floating city, buildings on
roads everywhere). A brief over ~2 hours is two briefs.

**Screenshots by milestone:** M1–M2 none (data checks and maps in `checks/`); M3 a high overview, one area, one street
level, one water edge (plus a hillside in a hilly city); the full standard set once per city at the end of M3 for the
user. Later milestones: the standard set for critic rounds, only the touched views for fixes.

## 2. The brief template

Every subagent brief contains:

- **Goal and done-criteria** (what "finished" looks like, measurable where possible) and the time box.
- **Paths:** the city folder, the data folder, exact coordinates or view names, files to read first.
- **Branch and worktree:** `.claude/worktrees/<agent>` (or your tool's equivalent), branch `<agent>`, based on which
  tip; whether it may commit.
- **Ports:** its own test-server port and Chrome debugging port (distinct ranges, e.g. servers 8790–8799, Chrome
  9350–9399), and the list of ports that are the user's.
- **Scratch:** a private folder named after the agent (absolute path) on disk, not in RAM-backed `/tmp`.
- **Machine rules:** the memory, lock and Chrome lines of §4, quoted, not just referenced.
- **No-touch list:** the user's servers and files, other agents' worktrees, files another agent is rewriting (e.g. the
  facade tables during a refactor), `main`.
- **Report shape:** what it did, the numbers (before/after), file paths, issues found, **peak memory**, every process
  left running (should be none), lock state, commits.

Many small briefs beat one long one. Spawn independent briefs in one message.

## 3. Agent concurrency and usage limits

- **Cap at ~3 builder/critic agents at once.** Five or more in parallel exhausted a weekly usage limit within two days
  of the multi-city run, and one builder sat idle for 5.5 hours on an API limit mid-milestone. Parallelism beyond
  what the machine's one-Chrome/one-heavy-stage rule allows only queues agents on the locks anyway.
- **Two model tiers.** Judgment work (building a milestone, every critic) on the capable tier; well-specified volume
  work (downloads, data copies, measurement runs, speed tests, docs) on a cheaper tier with a precise brief.
- **Fold user feedback into a running builder by message** (most agent tools can resume an agent with its context)
  instead of spawning a new agent that has to re-read everything.
- Critics are always fresh agents (`critique.md`); builders can be resumed.

## 4. Machine memory and the lock script

Numbers from a 15 GB laptop with an integrated GPU sharing system memory (Linux, systemd-oomd active):

| Thing | Memory |
|---|---|
| Chrome at about:blank | ~1.8 GB (16 processes) |
| Chrome with a full city loaded | **4–5 GB** more; shared GPU memory grows ~0.9 GB per load and ~2 GB per settled shot and is not returned |
| Heavy pipeline stage (footprints of a whole city, a DEM, tiles, packing) | several GB; a CityGML or LiDAR conversion of a whole city counts |
| Local Overpass import | peaks near 3 GB (container capped at 5 GB), ~15 min |

Rules that kept the run alive:
- **Across all agents: at most one Chrome with a city loaded and one heavy pipeline stage.** Start either only with
  ≥ 4 GB available (`free -m`, "available"). A guard kills a test Chrome under 1.5 GB available.
- **Restart Chrome with a fresh profile after two full-city views** (the GPU-memory creep above). Before a shot: if
  "shared" > 4,000 MB or "available" < 3,500 MB, restart first. Never shoot while a heavy stage runs.
- **Turn-taking:** hold the Chrome lock for one session (≤ 2 city views or one speed run), release, and wait ≥ 2 min
  before retaking it so waiting agents get a turn. Same for long pipeline sequences.
- **systemd-oomd** (most desktop Linux) kills the whole terminal session — every agent and the controller with it —
  when memory pressure stays high for ~20 s. That is the failure to design against.
- **`/tmp` and agent scratch may be tmpfs (RAM).** On the reference laptop `/tmp` was a 7.7 GB tmpfs holding 5 GB of
  shots and profiles at one point, which then counted against Chrome. Keep Chrome profiles, shots and big
  intermediates on disk (e.g. under `demos/data/`, git-ignored) and delete profiles when Chrome closes.
- **Disk:** check `df -h` before downloads over 1 GB; keep ~15 GB free. A local Overpass volume is 2–5.5 GB per city.
- **Speed tests need a quiet machine.** With the user's browser and two agent sessions holding ~4 GB, a city load left
  1.2–1.7 GB available and the guard aborted runs 2–12 times each; with 4 GB freed every load went through first time.
  A measurement taken under pressure is recorded as such, not as "passed".

**The lock script** (`scripts/lock.sh`) holds two machine-wide locks, `chrome` and `pipeline`, as files containing
`free` or `<PID> <owner> <time> <note>`:

```sh
scripts/lock.sh take pipeline b-tokyo-m3 "05a_terrain"   # exit 1 = busy: wait, retry every 60 s, never bypass
scripts/lock.sh pid pipeline <PID>                         # record the process it protects
scripts/lock.sh release pipeline                           # right after the stage ends, also on failure
scripts/lock.sh show
```

`take` warns when the holder's PID is dead (a stale lock: ask the controller, don't clear it yourself).
`speedtest.mjs` and `pixdiff.mjs` take and release the locks themselves (`--quiet` takes both).

Process hygiene that cost hours when missed:
- Record the **real browser PID** (a launcher wrapper's `$!` exits), kill only that PID after checking its command line.
- Never `pkill -f <pattern>` from an agent's shell: the pattern is in the shell's own command line and kills it. To
  search, bracket it: `pgrep -f "[c]hrome --user-data-dir=<dir>"`.
- Check the debugging port is free before launching (`ss -ltn`): a busy port means your shots go to an old Chrome.
- Never stop a process you didn't start. `sudo` and Docker commands are the user's; ask once, batched.

## 5. Worktrees, merging, linear history

- **One worktree per agent that writes code**, on its own branch. A pipeline agent gets its **own copy** of any data it
  rewrites (link raw inputs read-only; writing through a link clobbers the shared copy). In a worktree, recreate the
  git-ignored `web/` data links first.
- **Never commit on the default branch.** For several cities, either one branch per city **chained** so engine changes
  carry forward (city 2 branches from city 1's tip, city 3 from city 2's), or one integration branch that agents'
  branches land on. Engine work a later city needs earlier is its own branch, cherry-picked onto the current one.
- **Land by cherry-pick or rebase in a temporary worktree,** run the tests there, then `git merge --ff-only` the branch
  that servers and critics use. Never merge by hand in the tree a server is serving: a half-merged `main.js` once broke
  every critic's page load at once.
- **Prefer linear history** (recommended): easy to bisect a visual regression by serving each commit's engine
  (`testing-and-tooling.md` §4), easy to read. Note that GitHub's "Rebase and merge" refuses pull requests over 100
  commits; push a rebased branch and fast-forward instead, or squash per milestone.
- Code and data switch together: if a server serves the branch, regenerate or copy the data in the same step as the
  code that needs it.
- Keep the history light: check images only at a milestone's end, screenshots never (`eval/` ignored), generated
  settings in their own files. Three days of the multi-city run came to ~500 commits and 27 MB.

## 6. The hand-back protocol

A subagent hands back **only** when its done-criteria are met or it is blocked. If it must stop early (time box, usage
limit, a blocker), the report lists:
- what is done and what is not, item by item;
- the state: files changed, branch and last commit, uncommitted work, data written, locks held (should be none),
  processes running (should be none);
- the exact next command or step.

The controller then resumes the **same** agent by message when possible (it keeps its context) rather than briefing a
new one. The report is the only thing that reaches the controller: plain text after it is lost.

## 7. REPORT.md and Known issues

Each city keeps `demos/<city>/REPORT.md`, the build's log and the next builder's starting point:

- a one-paragraph scope, then a **Summary** table: milestone, wall clock, critic rounds (score, verdict per round);
- **one section per milestone, critic round and fix round**, titled with times and the agent, e.g.
  `## M8 critic round 2 (c-tk-m8-2, 05:00–06:05): 7 — one high (night reflections); closed after a narrow fix`. Each
  holds what was built, the numbers (before → after), decisions and their reasons, the stages to re-run;
- a **Known issues** table, appended at every close:

  | Milestone | View | What | Fix idea | Severity |
  |---|---|---|---|---|
  | M3 | Sumida, bridges | the bridges stand by OSM layers; they look low and flat | named decks per bridge | medium |
  | M2 | data | a tower completed this year has no outline in any source | hand-drawn outline from the developer's plans | high |

  Fixed items stay, marked `(fixed)` with where;
- a **"For M<n>"** list: what a later milestone must pick up (e.g. "For M4": the building types the facades must draw,
  the landmark figures needed).

Every milestone's brief starts from the REPORT's Known issues and "For M<n>" list; the critic does not see them.

## 8. The user's decisions file

During a long run the controller keeps one file of what needs the user, committed as it changes: downloads/accounts/
licences waiting; taste questions with options and a recommendation; **decisions the controller took for the user to
overrule** (each with the one config switch that undoes it); the final state (branches, servers still running and how
to stop them, what's next). The user reads it once on return instead of scrolling a session. Record the user's answer
in the same file.

## 9. The user-review round (after M10)

Plan for it: in the reference builds it came after every multi-city run and produced ~15 fixes in a day.
- Serve all cities from **one preview server** the user can open (one port, an index page linking each city's `web/`).
- The user batches notes with screenshots or `?view=` links. Reproduce each at **the user's camera** first
  (`testing-and-tooling.md` §4), fix, and re-shoot there and from four sides; send only the touched views back.
- A fix in shared engine code follows SKILL.md hard rule 6 (opt-in, or a pixel diff of every finished city).
- Each fix gets a REPORT entry and a commit message quoting the user's note.

Typical notes from the reference builds: a landmark's base drawn as an office block; bridge arches beside their deck;
parked cars across their bays; roofs too silvery; water a "static of white dots" at night; a dark band on the horizon
at dusk on one backend.

## 10. Publishing

A city's `web/` folder is static files, so any static host works. Steps that generalise:
1. **Resolve the links:** copy each `web/` with links followed (`rsync -aL --exclude '*.md' --exclude '.*'
   demos/<city>/web/ dist/<city>/`), so the host gets real files.
2. **A landing page** (optional): one page listing the cities, built from a small JSON of per-city copy (title,
   tagline, facts, captioned shots, start views as `?view=` links) and a media folder.
3. **Dry-run** (build `dist/`, count files and size, load it locally), then **deploy only on the user's go**.
4. **The deployed copy becomes the regression baseline:** later engine changes are pixel-diffed and speed-tested
   against it (`speedtest.mjs --ref`, hard rule 6). Keep the commit it was built from.

**Credits.** Open data licences require attribution (OSM's ODbL: "© OpenStreetMap contributors"; CC BY sources by
name). Two ways, the builder's choice: a small credit line in a corner of the view (always visible, the safest
reading of the licences), or credits in the viewer's About panel plus the landing page (a cleaner picture; the
reference builds chose this, with every source and licence listed in About). Either way, list every dataset.

**Worked example: Cloudflare Workers static assets.** One Worker serving every city under `/<city>/`:

```jsonc
// wrangler.jsonc
{
  "name": "my-cities",
  "compatibility_date": "2026-09-01",
  "assets": { "directory": "./dist", "html_handling": "auto-trailing-slash", "not_found_handling": "404-page" },
  "routes": [{ "pattern": "cities.example.com", "custom_domain": true }]
}
```

`npx wrangler@4 deploy` uploads only files whose content changed. Auth with an API token in a git-ignored `.env`
(the browser login can fail from a datacenter or proxy address). Limits to plan around (free plan, at the time of
writing): **20,000 files per version** (a large city's tiles, blocks and markings can run to thousands of files:
count them in the dry run), **25 MiB per file**, static asset requests free. Other good fits: GitHub Pages (1 GB site
limit), Netlify, any S3-style bucket behind a CDN; serve `.glb`/`.bin` with compression where the host allows.

## 11. Data servers

For a big city the public Overpass servers answer 429/504 for hours. The default for anything beyond a few districts
is a **local Overpass** in Docker (`scripts/local-overpass.sh`; recipe and caveats in `data-sources.md`): download the
extract first (BBBike or Geofabrik, placed where the script expects it), one import at a time with ≥ 6 GB available
(~15 min, ~3 GB peak), put `http://127.0.0.1:<port>/api/interpreter` first in city.toml's `overpass` list, check one
count against a public server, and stop and remove the containers and volumes when the build is done. Query results
are cached in `raw/overpass_cache`, so a re-run doesn't need the server.
