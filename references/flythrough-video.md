# A fly-through video of the city

How to turn a finished city into a cinematic video (a post, a demo reel) without screen recording. The viewer has
filming hooks (`engine/viewer/main.js`, `__viewer.film`); the script that drives them is yours to write in the city's
`eval/` (a Node script, no dependencies beyond `ffmpeg`; New York's in the reference builds was a few hundred lines:
a keyframe table, the path baking below, a CDP connection and the ffmpeg pipe). This page is its specification.

## How it renders

The viewer draws on demand and a full-quality frame costs 0.2–0.5 s on an integrated GPU, so a live recording
would stutter. Instead the script renders **frame by frame** over the DevTools protocol and pipes JPEGs into ffmpeg:

1. Start a Chrome with a debugging port (`testing-and-tooling.md` §2b, WebGL 2 or WebGPU; take the chrome lock),
   serve `web/` on your own port.
2. The script connects, sets the viewport to the output size at device scale 1, loads `?view=<first place>`, waits
   for `window.__ready`, calls `__viewer.film.hide()` (menu and HUD off).
3. It bakes the camera path (below), asks the page for terrain heights along it once, clamps the camera above the
   ground, and calls `__viewer.film.prime(samples)`: a sweep along the path so the tiles, trees, rooftops and cars
   that stream by distance are cached and every shader (day and dusk) is built; it ends back at the start.
4. Per frame: `film.setClock(i / fps)` (waves and traffic take their time from this clock, so a frame that takes a
   second to draw still moves the water by a thirtieth), then `film.frame({ position, target, hour })`, which draws
   **one settled frame at once** (full resolution, fresh shadows, the glass's city probe captured again) and resolves
   when the GPU has finished it; then `Page.captureScreenshot` → ffmpeg's stdin.
5. ffmpeg: `-f image2pipe -framerate 30 -i - -c:v libx264 -pix_fmt yuv420p -crf 18 -preset slow -movflags +faststart`.
   The master comes out large (New York: 449 MB for 2:18 at 1080p); make the upload copy with
   `-crf 22 -maxrate 12M -bufsize 24M` (170 MB, within X's 512 MB / 1080p limits).

Speeds seen: 0.2 s a frame at 960×540, 0.25–0.35 s at 1920×1080 on an Iris Xe (a 138 s video in 17 minutes).
`--preview` (5 fps, 960×540) renders a whole route in a minute or two: **always preview first**, and look at the
frames as a contact sheet (`ffmpeg -vf "fps=0.5,scale=480:270,drawtext=text='%{pts\:hms}'...,tile=4x6"`) plus a
1 fps sheet of any tricky stretch (a crest, an underpass, the ending) and the very last frame.

The viewer-side hooks (`film` in main.js) do four things a script can't: draw settled at once (the loop normally
waits 250 ms after the last change), take a virtual clock, lift the map controls' 86° polar limit (a path may look
up, under a bridge deck: with the limit the controls pushed the camera above whatever it looked at, and an
"underpass" rode on the roadway), and prime the streams. They have no effect until called.

## Designing the route

Agree the beats with the user first (a list of places and one or two shots each), then the length: **the route's
length is set by its geometry, not by wish.** Add up the distances between the beats, divide by cinematic speeds,
and tell the user before building. New York's route (Statue → harbour → WTC → Empire State → Central Park → down
the East River under the bridges → harbour finale) is 31 km; at 200–350 m/s that is 2 min 18 s, and "65 s" would
have been a missile. `--seconds` can play a route faster or slower, but the natural length should be the default.

Camera rules that survived the user's review (each was a complaint first):

- **Fly like a bird: always forward.** The look-at is the camera's own position 2.5 s ahead on the path (clamped
  to 150–600 m), pitched 5–15° down (more when high). Never pin the view on a landmark while the camera moves
  round it: the user called that "rotating at a fixed point". A helix up a tower works with this rule: the tower
  sweeps past on one side; an inward yaw bias of up to 30°, eased in and out, keeps it in frame more.
- **Smooth the heading.** Low-pass the path's heading over ~3 s (pitch 2 s), cap the yaw rate at ~12°/s outside
  the planned turns (40°/s inside them), and never let the keys zig-zag: a shore leg with keys stepping left and
  right every 300 m made the view wag.
- **Speeds:** 200–350 m/s over water and at height, 150–200 low and near things, 100 or less through turns, easing
  at the beats. Peak speed and steepest pitch printed in the route summary.
- **Heights:** 12–15 m over water for an underpass, 25 m above the ground at the least over land (the script
  clamps), 250–450 m over dense blocks so no tower comes within 110 m with its roof above the camera (the script
  checks). Low flying near buildings from a guessed shoreline hit a facade; when unsure, fly higher: at 150 m
  mid-river both banks are in view and nothing can be hit.
- **Bridges:** cross them along the river (square on to the deck) near mid-span: under the deck at 12–15 m over
  the water, or over it 20–25 m above the roadway, below the cables' saddles. Read deck heights from
  `roads.gpkg` (the ways with `span = <bridge>` carry z), not from memory. Mix them (under, over, under).
- **Turns have a geometry.** A right turn from heading H ends to the right of where it started; you cannot exit
  a right turn heading north from a point west of your entry. Work the exit point back from the end frame (the
  end position minus a straight glide along the end heading), then the arc's centre (to the inside of the turn
  at the exit), then the entry (where the arc's tangent matches the approach). Do this on paper before rendering.
- **Stay over the city.** Never fly over the flat backdrop suburbs or the far edge of the model, and keep the view
  off them too: the user's "don't show Queens" was a 185° turn that faced the empty side of the harbour for ten
  seconds. Plan every turn so what it faces is the part of the city the video is about.
- **The ending is a frame the user picks.** Ask for a screenshot of the resting view (the viewer's HUD and the
  place presets make this easy), reproduce its bearings (what is left, centre and right of the frame, how far
  down the foreground is), and place the rest point from that. New York's: 700 m south-west of the Battery's tip,
  470 m up, facing north-east: the Battery at the bottom, the WTC 25° left, both lit bridges 20° right.
- **Coming to rest.** Speed decays to zero over the last 6 s; from 10 s before the end the view is drawn onto the
  aim point and held for the last 4 s. Hold the path heading of the moment the aim begins: the look-ahead of a
  near-zero velocity is noise, and it swung the view left and right at rest.
- **Light:** most of the flight in the afternoon light the city was tuned for; the last beat a quick eased sunset
  (to the hour of sunset in the first 5/13 of the beat) and a slow hold in the blue hour to the end, so the windows,
  streets and bridge necklaces are lit for the last 20–30 s. The whole light change is a few seconds of time-lapse;
  it reads fine. Cars only exist within 3 km of the camera, so a resting shot wants its traffic within that.
- **Openings:** a slow first shot (a landmark passed at 120–200 m/s from 500 m out); a fast, featureless first
  two seconds read as "noise" to the user.

## Workflow that worked

- One agent owns the keyframe table (a small Node script, no browser needed, can recompute route length, per-beat
  peak speeds, steepest pitch, lowest heights and yaw rates from the table alone); the coordinator renders previews
  and reads the sheets. Give the agent exact coordinates and constraints (scene metres from `tiles.json`'s
  `views`, tower positions from the landmark tables, shorelines from `ground.gpkg`'s `land` layer), never "about
  here". Expect it to report where the brief's numbers contradict each other, and answer with numbers.
- After each preview, list the faults by time code, fix only those, preview again. Six to ten previews is normal.
- The user reviews previews too (serve the folder they are written to); the final render only after "now make the
  video".
- Retakes: `--start S --end E` renders a range into its own file with the same clock, so the water phase matches.
- Keep the rendered `.mp4`s out of git (ignored, e.g. in `eval/`); commit the script and its keyframes.

## Pitfalls met

- `Array.from({ length }, (_, i, a) => …)`: the callback has no third argument; compute the count first.
- The map controls' polar limit (above) and their damping: `film.frame` sets the camera and target and calls
  `controls.update()` once; nothing else may move the camera between frames.
- The probe and the shadow map: `film.frame` marks the glass probe stale every frame (20–30 ms, fine offline) and
  forces a shadow refresh, so reflections and shadows never lag the camera; without it the first frames after a
  jump mirrored the previous place.
- Rendering runs on the user's display when the test Chrome uses their X session: they will watch your candidate
  frames, so don't leave odd test views on screen.
- `pkill -f <pattern>` from the shell tool kills the shell itself when the pattern is in its own command line;
  kill by recorded PID.
