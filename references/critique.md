# Independent critique

Every milestone ends with a critique by a subagent that did not build it. The builder is too used to its own
output; the user's early feedback on the first reference build, Shenzhen ("the tall buildings look like light blue
blocks", "trees and water are colour blobs", "too glassy", "the lighting is pixelated", "it glitches when
switching") was each time something a fresh look at a screenshot next to a photo would have caught. The critic's job
is to be that look.

## Rounds and closing (the default that worked across eight cities)

- **Two critic rounds per milestone.** Round 1 → fix round → round 2 (a new critic). Most milestones in the
  reference builds went 6 → 7; a third round rarely bought more than the time it cost.
- **One narrow fix, no new critic,** when round 2 leaves exactly one high finding: fix that item only, check it
  yourself at the critic's view, and close.
- **Then close.** Everything left goes to the city's REPORT under Known issues — milestone, view, what, fix idea,
  severity — and is carried into the next milestone's brief ("For M<n>"; `running-a-build.md`). Never hold the
  run on a medium finding.
- **Parallel milestones, one critic.** When milestones were built side by side (M4 landmarks ∥ M4 facades, M5 ∥ M6),
  one critic can judge them together and **score each separately**, so each closes on its own.
- M1–M3 are judged on geometry and correctness only; materials count from M4.

## Evidence the builder hands over

1. **Screenshots** at 2× device pixel ratio (most viewers' laptops are 2×; aliasing and shimmer only show there),
   with the menu and the stats line hidden (the stats line is off by default; turn it on, or read the numbers from
   `__viewer`, when a shot is evidence of idle or draw counts), from:
   - the **standard views** (fixed for the whole project, same camera every milestone so rounds compare):
     overview from high (≈12 km), each area preset (districts, CBD, waterfront, old town, airport/port), a street
     level view (≈40 m up, looking along a street), a waterfront view across water, a hillside view if there are
     hills, and the landmark presets;
   - milestone-specific views (dusk and night for M8, see "Night and dusk checks"; a slow pan recorded as frames for
     M9);
   - **the user's items** (below), each at the user's own camera;
   - a **before** shot of the same view from the last round, side by side (`compare_*.jpg`, before on top).
2. **Numbers**: fps and draw calls/triangles at the standard views (still, moving, animating), time to first frame,
   time to usable view, longest main-thread task after that, total download and request count, idle state
   ("idle" = nothing drawn), all at 2× and on both backends where relevant. Anything that got worse since the
   last milestone is called out.
3. **What the milestone set out to do** (one paragraph) and what is invented vs from data.
4. **User items**, when the user has given feedback: the user's words verbatim and the camera they looked from (a
   URL with `?view=` or the position/target/hour), one item each.

The builder does **not** hand over its own assessment, its reasoning, or the previous critic's text.

## The critic's brief (prompt template)

> You are a demanding art director and graphics engineer reviewing a milestone of a browser 3D reconstruction of
> <CITY> (<districts>). Goal of this milestone: <goal>. Real vs invented: <notes>.
> Screenshots: <paths, each with its view name>. Numbers: <table>. Budget: <budget table below>.
> First find reference photos yourself: for each view, search the web for aerial / drone / street photos of that
> place (and of each landmark), and note the URLs you used. Compare what a person who knows <CITY> would notice:
> - does it read as <CITY> at a glance (skyline, scale, colours, density, streets, water, hills)?
> - materials: flat colour blobs, plastic or over-glossy glass, wrong colours (e.g. neon lawns), tiling or
>   repetition, pixel noise/shimmer/moiré, banding, missing shadows, z-fighting, floating or buried objects,
>   buildings on roads, seams at tile or data edges, odd landmark shapes;
> - the far view as much as the near view; day and (from M8) dusk/night;
> - performance against the budget, and anything that would make a laptop hot (drawing while idle, animation
>   out of view).
> User items: <the user's words + camera, one per item>. For each, shoot the user's camera yourself and orbit the
> place from four sides; rule it fixed / half-fixed / not fixed. Half-fixed counts as a high finding. A description
> ("the figure is centred on the outline") is not evidence; the picture from where the user stood is.
> Return JSON: `{"verdict": "pass"|"revise", "score": 0-10, "findings": [{"severity": "high|medium|low",
> "view": "...", "what": "...", "why it looks wrong (vs which reference)": "...", "fix idea": "..."}]}`,
> worst first, at most 12 findings, no praise, plus `"user_items": [{"item": "...", "status": "fixed|half|not",
> "evidence": "<shot>"}]`. When several milestones are judged together, one verdict and score per milestone. Pass
> only if a local would accept it as their city at a glance in every standard view, no high-severity finding is
> left, and every budget line holds.

Use a capable model for the critic (the same tier as the builder), with web search and image reading enabled.

## Rubric (what the score means)

| Score | Meaning |
|---|---|
| 9–10 | Could pass for a stylised aerial photo in most views; nothing jumps out |
| 7–8 | Clearly the city; a few materials or distant areas give it away as CG |
| 5–6 | Right geometry, but materials read as a game from ~2010: blobs, plastic, flat lighting |
| 3–4 | Artefacts dominate: floating/buried objects, flicker, missing layers, wrong scale |
| 0–2 | Doesn't load, or doesn't read as the place |

Pass bar: **score ≥ 7, no high-severity finding, every budget line met.** For M1–M3 (data milestones) judge
geometry and correctness only; materials start counting from M4.

## Why the user's camera matters

In the Tokyo build the critic accepted two fixes the user then raised again: Tokyo Tower's base (it straddled a
pale windowed office block that is really the tower's FootTown podium) and the Sumida's bridges (arches off their
decks, deck ends cut over the approach roads). Both had been checked from the critic's standard views and "looked
fixed"; from the user's angle they were not. Since then the critic re-shoots each user item at the user's camera and
from four sides, and a half-fix is a high finding.

## Night and dusk checks (M8, and any milestone that touches light)

- **Dusk by the sun, not the clock:** the menu's Dusk preset (the sun ~4.5° down), plus steps through the blue hour
  (e.g. 18:30, 19:00, 19:30, 20:00, 21:00 local in autumn).
- **A light-change sequence:** 6–8 changes of light in one load (day → dusk → night → day → night ...), ending at
  night, with a shot after each. Off-screen captures that go wrong (a glass reflection probe, the bloom) show up
  only after several changes: bright bloom orbs, black towers, black rectangles.
- **Water at night** from 20–60 m and from 300 m+: mirrored lights should be streaks, not grain or a white sheet.
- **Roofs and walls at dusk:** compare the blue/red ratio of roof and wall pixels at dusk and at night. In
  reference builds the blue hour from the air came out darker and bluer than the night itself until the dusk grade
  was fixed.
- Rubric lines: "dusk walls and roofs no darker or bluer than night"; "mirrored lights as streaks, not grain";
  "no black blocks, no bloom orbs after a light-change sequence"; "towers not uniform pale clay from the air".

## Budget (the reference builds measured these; hold a new city to the same)

| Measure | Budget |
|---|---|
| Idle, nothing moving in view | 0 frames drawn ("idle" in the stats line) |
| Animation (waves/traffic in view) | ≤ 24 fps, half after 30 s without input, stopped after 180 s |
| Time to usable view (home connection ≈ 80 Mbit/s, 30 ms) | ≲ 12–15 s |
| Everything loaded | ≲ 20–30 s |
| Longest main-thread task once usable | ≲ 350 ms |
| Settled frame, 2×, mid-range laptop GPU | no worse than the previous milestone by more than ~10 % unless the user agreed |
| Draw calls, city view | a few hundred (tiles merged per material; instancing for trees, cars, rooftop items) |
| Change of light (day/dusk/night) | no flicker; after warm-up, no visible wait |
| Daytime cost of night-only features | ≈ 0 (measured) |

## Builder's side of the loop

1. Sort findings by visual gain per cost; take the high ones and the cheap medium ones. Never "fix" a finding by
   hiding a layer or lowering quality globally without saying so.
2. Fix, run the pipeline checks (and `city3d stale` after any single stage), re-shoot exactly the same views,
   update the before/after compares. **Look at every shot yourself before the critic does**: floating or missing
   things (New York's rooftop clutter hanging over every district after a terrain rebuild) were in many shots
   and the user saw them first.
3. Spawn a **new** critic with the new evidence (not the old critic's text). Two rounds, then the narrow fix or
   close (above); the rest goes to Known issues.
4. Checkpoint to the user: score and verdict, 2–4 compare images, numbers, what's left, what's next.
5. Put the lessons where the next city will find them: the REPORT entry, commit messages (what and why, with
   numbers), the city README, and — if it is general — this skill's references.
6. After the rounds, fixes from the user's feedback are re-shot only in the views they touch (a full set cost
   New York about 50 minutes with a 4–5 GB Chrome); say which views to look at, and give each the user's camera.
