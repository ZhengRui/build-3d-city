# Testing and tooling

How the reference builds were tested visually and for performance, by agents on Linux machines with a slow
integrated GPU (Intel Iris Xe) while the user watched on a MacBook (WebGPU, 2× Retina) and a phone. Scripts:
`scripts/cdp.mjs`; the all-cities speed test `scripts/speedtest.mjs` and the pixel diff `scripts/pixdiff.mjs` (§5);
the machine locks `scripts/lock.sh` (memory rules: `running-a-build.md` §4). Test handles: `viewer-architecture.md` §7.

Where things go: screenshots and measurement output in the city's `eval/` (git-ignored; commit only notes and the
scripts) or under `demos/data/` when large; never in a RAM-backed `/tmp`. The viewer starts with the menu folded and
**the stats line hidden**: for evidence of idle, fps or draws, turn Stats on in the menu or read `__viewer.frames()`.

## 1. Ground rules

- **Never touch the user's things.** Their preview server, their
  browser, their tabs, their screensaver settings. Read only. Ask before overwriting data their server serves.
- **Own port per agent** (e.g. 8762 and up), check it's free (`ss -ltn | grep :8763`), record the PID, and kill **only
  that PID after verifying it** — never by pattern, never from a shared pid file:
  ```sh
  python3 -m http.server 8763 --bind 127.0.0.1 -d demos/<city>/web > $SCRATCH/srv.log 2>&1 & echo $! > $SCRATCH/srv.pid
  P=$(cat $SCRATCH/srv.pid); ps -o pid,args -p $P | grep -q "http.server 8763" && kill $P
  ```
  In a git worktree, recreate the git-ignored `web/` data symlinks first (absolute paths to the shared data, read
  only); an agent that rewrites data gets its own copy.
- **Memory before every load.** A city in Chrome takes 4–5 GB on top of a bare Chrome's ~1.8 GB. Take the chrome lock
  (`scripts/lock.sh take chrome <you> "<note>"`), check `free -m` shows ≥ 4 GB available, never shoot while a heavy
  pipeline stage runs, restart Chrome with a fresh on-disk profile after two full-city views, and release the lock
  when Chrome is closed (`running-a-build.md` §4). Timings taken under memory pressure are recorded as such.
- **Test both backends when shaders change.** Headless and most VMs have no WebGPU → WebGL 2 fallback. Bugs differed:
  the day/night flicker from non-instanced stand-ins only reproduced on WebGPU.
- **Test at 2× device pixel ratio** at the user's window size (e.g. 1744×970 CSS px) with Resolution 2×: aliasing,
  shimmer and the night "pixel mosaic" only show there, and it is 4× the pixels of a 1× test (performance!).
- Say what you could not test (e.g. "WebGPU path checked by reading three's source only") in the report.
- **No warning is harmless.** New York took a WebGPU depth-texture validation error seen from M3 on as harmless
  until M4; it was making three's async pipeline creation fail at random (cars, facades, shadows or the probe
  missing on some loads: `tsl-and-three-pitfalls.md` §36). Chase every new console warning when it appears.
- **Look from where people look.** Straight-down test views hid hollow cars (their front and rear faces culled)
  for three milestones; shoot every layer from street level and an oblique view too.
- **Look at every screenshot yourself** before handing them to a critic or the user: floating rooftop clutter
  (stale layers after a terrain rebuild) was in many of New York's shots and the user saw it first.
- **Waiting on a background job:** `pgrep -f pattern` in a wait loop run through a shell tool matches that shell's
  own command line (it holds the pattern) and never ends; New York had such loops spin for hours and block a
  shoot. Wait on a file the job writes, on its recorded PID (`kill -0 $P`), or bracket the pattern
  (`pgrep -f "[c]hrome"`).

## 2. Browsers

### a. chrome-devtools MCP (preferred when available)
Load tools via ToolSearch (`new_page`, `navigate_page`, `evaluate_script`, `take_screenshot`,
`list_console_messages`, `emulate`, `performance_start_trace`/`stop_trace`, `list_network_requests`, `close_page`).
- The browser is **shared with other agents**: open your page with `new_page({ url, isolatedContext: "<agent>-<port>",
  background: true })` and pass your `pageId` explicitly on every call, or screenshots come from another agent's tab.
- `navigate_page` with `ignoreCache` after code changes; close your page when done.
- `emulate` sets a viewport with `deviceScaleFactor: 2` (persists for the page) and network presets (mobile-ish
  only — for home-broadband numbers use the throttling server below).
- A long `performance_stop_trace` once **crashed the shared browser** and every agent's pages in it. Prefer CPU
  profiles via CDP (`cdp.mjs profile`) for long captures.

### b. Standalone Chrome + `scripts/cdp.mjs` (when the MCP is missing, broken or shared)
```sh
S=$SCRATCH   # a scratch dir of yours
google-chrome --user-data-dir=$S/chrome-test --remote-debugging-port=9333 --no-first-run --no-default-browser-check \
  --window-size=1280,800 \
  --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows \
  about:blank > $S/chrome-test.log 2>&1 & echo $! > $S/chrome-test.pid
# WebGPU on Linux (Vulkan through ANGLE):
#   --enable-unsafe-webgpu --enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan --use-angle=vulkan
# a 2x screen: --force-device-scale-factor=2   (window size stays in CSS px)
node cdp.mjs nav "http://127.0.0.1:8762/?view=Futian%20CBD&waves=0&traffic=0"
node cdp.mjs eval "(async () => { while (!window.__ready) await new Promise(r => setTimeout(r, 500)); return document.getElementById('stats').innerText; })()"
node cdp.mjs shot $S/cbd.png
node cdp.mjs console 3000
node cdp.mjs profile "(async () => { /* the action to profile */ })()"
P=$(cat $S/chrome-test.pid); ps -o pid,args -p $P | grep -q chrome-test && kill $P
```
- Check WebGPU really is on: `node cdp.mjs eval "(async () => { const a = await navigator.gpu?.requestAdapter(); return a?.info; })()"`
  (got `{vendor: "intel", architecture: "gen-12lp"}`), and the stats line says `WebGPU`, not `WebGL 2`.
- Each `cdp.mjs` call is a fresh DevTools session: page state persists, **session emulation doesn't** (use the Chrome
  flags, or do the whole measurement inside one `eval`, or write a one-off Node script holding the session — the
  loading measurements used one that set `Emulation.setDeviceMetricsOverride({ width: 1440, height: 900,
  deviceScaleFactor: 2, mobile: false })`, `Network.setCacheDisabled`, and
  `Page.addScriptToEvaluateOnNewDocument(probe)` before navigating).
- Headed runs: `Page.bringToFront` and `Emulation.setFocusEmulationEnabled({ enabled: true })`, or rAF throttles.
- **A sleeping display throttles Chrome to ~1 fps** and ruins timings. Check (`xset q`) and ask the user rather than
  changing their power settings; one agent woke the display with `xset dpms force on` and left the screensaver
  timeout off — if you must change it, restore it exactly and tell the user. For frame-rate measurements start the
  test Chrome with `--disable-gpu-vsync --disable-frame-rate-limit` instead: frames then come as fast as the page
  and GPU allow, display or not (Paris M9: 1.2-1.6 fps on a sleeping monitor, 8-22 fps with the flags, settled GPU
  times unchanged). Tell-tale: an empty WebGPU canvas's `requestAnimationFrame` exactly every 1,000 ms.

### Linux: getting a real GPU (WebGPU) when nobody is at the machine
Headless Chrome here gets no WebGPU adapter and renders WebGL in software (SwiftShader/llvmpipe: a city takes
60-75 s to load, a night frame ~2 min). A GPU needs a **logged-in desktop session**:
- No session (e.g. after the user was logged out, or a memory kill took the desktop with it)? Ask the user to log
  in remotely: GNOME Remote Login over RDP (`sudo grdctl --system rdp enable`, `set-tls-key`/`set-tls-cert` with a
  self-signed pair made as the `gnome-remote-desktop` user, `set-credentials <user> <password>`, restart
  `gnome-remote-desktop`; the RDP credential is separate from the Linux login). Use a FreeRDP-based client
  (FreeRDP/Remmina, or Windows' `mstsc`): Microsoft's Mac client fails GNOME's hand-over to the login screen
  (black screen, "Message Integrity Check" in the server log).
- A remote session isn't on the physical seat, so logind doesn't grant it the GPU: the user must be in the
  `render` (and `video`) group (`sudo usermod -aG render,video <user>`, the user's call); launch Chrome through
  `sg render -c "…"` until a fresh login picks the group up. Symptom otherwise: adapter "swiftshader"/llvmpipe.
- Chrome's Wayland mode can't use Vulkan: use the session's Xwayland — `DISPLAY` and `XAUTHORITY` from the
  session's `gnome-shell` environment (`tr '\0' '\n' < /proc/$(pgrep -n gnome-shell)/environ`) — with
  `--ozone-platform=x11` plus the WebGPU flags above.
- Keep the session from blanking/locking (it throttles Chrome): `gsettings set org.gnome.desktop.session
  idle-delay 0`, `gsettings set org.gnome.desktop.screensaver lock-enabled false` (with
  `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus`), and tell the user you did.
- Confirm with `SystemInfo.getInfo` over CDP (the device string names the real GPU; `webgpu: enabled`) and the
  adapter check above. Measured: Futian CBD usable in 12 s, loaded in 15 s, waves at 17 fps on an Iris Xe.

### c. Headless one-shot screenshots without a GPU (early milestones)
```sh
google-chrome --headless=new --user-data-dir=$S/chrome-h --use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader \
  --window-size=1400,900 --virtual-time-budget=120000 --screenshot=$S/v1.png "http://127.0.0.1:8763/?view=Shekou"
```
SwiftShader (CPU) WebGL 2: slow, fine for "does it load and look right", useless for timings. Headless with a GPU:
`--headless=new --enable-gpu --use-angle=gl-egl --ignore-gpu-blocklist`.

## 3. Driving the viewer in tests

Install helpers once per page (then call them from later `eval`s):
```js
(() => {
  const v = window.__viewer, wait = (ms) => new Promise((r) => setTimeout(r, ms));
  document.getElementById('menu').style.display = 'none';            // clean screenshots
  window.go = async (x, z, d, el, az = 200, ms = 5000) => {           // look at (x, z) from compass az, elevation el
    const t = v.controls.target; t.set(x, v.terrain.height(x, z), z);
    const a = az * Math.PI / 180, e = el * Math.PI / 180;
    v.camera.position.set(x + Math.sin(a) * Math.cos(e) * d, t.y + Math.sin(e) * d, z - Math.cos(a) * Math.cos(e) * d);
    v.controls.update(); v.invalidate({ shadows: true }); await wait(ms);   // wait for the settled frame
    return document.getElementById('stats').innerText;
  };
  window.setHour = async (h, ms = 3000) => { const s = document.getElementById('s-time'); s.value = h;
    s.dispatchEvent(new Event('input', { bubbles: true })); await wait(ms); return v.night.state.lights; };
  window.button = (label) => [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === label).click();
  return 'ok';
})()
```
- Wait for `window.__ready` (everything loaded) and, for day/night tests, `__viewer.warmLeft() === 0`.
- Deterministic shots: `?waves=0&traffic=0`; the sky's clouds drift, so exclude the sky (or accept tiny diffs in sky
  and glass) when diffing. Same URL, same camera, same hour, same window size, same dpr for before and after.
- `__viewer.idle(s)` pretends s seconds without input (tests the 30 s / 180 s animation rules without waiting).
- Timing a change of light: click `Night`, poll `#freeze.hidden` every 30 ms, report click-to-uncover ms; after
  warm-up expect ~one frame and no note.

## 4. Standard views and before/after compares

- Fixed for the whole project (critique rounds compare like with like): every area preset, every landmark preset,
  an overview (~12 km), a street-level view (~40 m up along a street), a waterfront across water, a hillside, and for
  night work the same views at 18:00 and 21:00. Shenzhen's set: `Futian CBD`, `Shenzhen Bay`, `Qianhai`, `Shekou`,
  `Bao'an Center`, `Xixiang old town` (urban village), `Airport`, `Wutong Island` (ponds, trees), the landmark
  presets, a low oblique CBD view at 1.4–1.7 km (the user's favourite angle), Houhai across the bay (night mirror),
  a park at 260 m, a street at 180 m / 70 m, a forest at 1.2 km, the whole bay at 3 km, an 8 km far view.
- Dusk shots use the menu's **Dusk** preset (the sun 4.5° down), not a clock hour: with clock time (`time.utcOffset`)
  New York's 18:00 "dusk" was before sunset.
- **Scale the shoot to the change.** A full set is expensive: New York's 58 shots (29 views, day and night) took
  about 50 minutes, with a Chrome holding 4–5 GB of a 16 GB machine (restart it with a fresh profile every two
  full-city views: GPU memory creeps). Critic rounds need the full set; fixes
  after them (the user's feedback) need the one or two views they touch, and the user may prefer to look
  themselves.
- Reproduce the user's screenshot angle first when they report something; crop and upscale their image and yours
  with nearest-neighbour to compare pixel-level issues (mosaic, shimmer).
- Baseline: serve the old commit from a second worktree on another port, shoot the same views, stack before over
  after:
```python
from PIL import Image, ImageChops
import numpy as np
a, b = Image.open('before_cbd.png').convert('RGB'), Image.open('after_cbd.png').convert('RGB')
out = Image.new('RGB', (a.width, a.height * 2)); out.paste(a, (0, 0)); out.paste(b, (0, a.height))
out.save('compare_cbd.jpg', quality=90)
d = np.asarray(ImageChops.difference(a, b)).max(axis=2)
print('mean diff', d.mean().round(2), '% > 2 levels', (d > 2).mean() * 100, 'max', d.max())   # "day unchanged" check
L = np.asarray(b.convert('L'), float)
print('luma p10/25/50/95/99', np.percentile(L, [10, 25, 50, 95, 99]).round(1))
m = (L > np.percentile(L, 15)) & (L < np.percentile(L, 40))
print('dark mid-tones rgb', np.asarray(b, float)[m].mean(0).round(1))                         # "veil" check
a.crop((1100, 380, 1500, 630)).resize((1200, 750), Image.NEAREST).save('crop_before.png')      # pixel-level look
```
  Thresholds used: "daytime unchanged" = max 8/255 on ≤ 0.3 % of pixels (or mean ≤ 0.12 levels); a night veil shows
  as dark mid-tones drifting warm/brown; a lost mirror as lower water percentiles.
- **Check a shared-viewer change on WebGL 2 too, at a dusk or night start and while moving, against the deployed
  copy** (a New York regression check). The "New York unchanged" checks after the Paris/London/Berlin rounds were
  settled frames on WebGPU in daylight; the user then found a black and white line along the sea's horizon at
  Downtown Brooklyn at dusk on WebGL 2. It was on WebGPU too, at every load and after every change of light, for a day:
  the warm-up fix (`performance-and-loading.md` §12) had moved the sky map's remake into code that only ran inside compileOnly's dry rounds, where
  nothing is drawn, so water and glass reflected an empty map (fixed in updateEnv). How it was found:
  - the deployed copy is the baseline the user knows. A local copy of it can be incomplete on disk, so serve the
    engine at the commit it was built from instead: `git archive <commit> <path to engine/viewer> | tar -x
    --strip-components=<depth>` into scratch, with city.json and data links beside it. Compare the data first (md5
    of tiles/ and blocks/). Record the commit every deploy was built from.
  - bisect by serving each candidate's engine over the same data from one server (one folder per commit), screenshot
    the view, and test the result automatically (here: the first dark row in a column of the sky, `< 25` luma).
    Some old commits may show an empty page in a Chrome without WebGPU flags (a black-page bug in the reference
    history): use `?webgl=1` for every bisect point.
  - set the user's resolution through localStorage before the load (`<storagePrefix>.resolution`, CDP
    `Page.addScriptToEvaluateOnNewDocument`), and the viewport with `Emulation.setDeviceMetricsOverride` in the same
    CDP session as the measurement (it ends with the session).
  - moving frames: mouse drags over CDP (`Input.dispatchMouseEvent`, right button orbits, left pans) give the user's
    feel, but the same input can take two viewers to different places; for numbers move the camera from the page
    instead (a fixed orbit and pan, `invalidate()` per step, waiting for `__viewer.drawn()` to change) and read
    `__viewer.frames()`. Its `draws` are the last render call's, so a moving frame drawn through the settled pipeline
    does not show as more draws: compare its GPU `ms` too. At Downtown Brooklyn at dusk, 1.5x: the 30 Sep viewer's
    moving frames 108-120 ms and ~133 draws, now 126-138 ms and ~130 (the cost grew in steps over the Paris build, not
    in one commit); the 30 Sep viewer's animating frames ("waves + traffic 3 fps, 102 draws") are a plain render, not
    a moving frame.
- **The user's camera first.** When the user reports something, reproduce their exact view (their `?view=` link, or
  position, target, hour and window size), fix, and re-shoot there and from four sides before calling it fixed
  (`critique.md`, "Why the user's camera matters").

## 5. Performance measurement

### The speed test: every city, after every viewer change (`scripts/speedtest.mjs`)

One tool for every city in the project, so that a fix for one city can't quietly slow another. Run it before committing any
viewer change (the engine's viewer is shared: a Paris fix runs in New York too) and compare with the saved baseline:

```sh
cd .agents/skills/build-3d-city/scripts
node speedtest.mjs --cities paris,berlin --baseline <project>/demos/data/speedtest/baseline-webgpu.json
node speedtest.mjs --full --cities berlin                  # + layer split, first minute, idle (~20 min a city)
node speedtest.mjs --save-baseline <file>                  # after an accepted change: this run's cities replace theirs
node speedtest.mjs --cities nyc --webgl --ref <deployed copy>/nyc   # an older copy against this tree
```

- **What it does.** Serves the tree it lives in (`python3 -m http.server --port`, default 8795, its PID in the JSON;
  `--url` for a running server), and per city starts its own GPU Chrome (`--cdp-port`, default 9355; fresh profile
  under `demos/data/.chrome/`, deleted on close; the real browser PID in the chrome lock; vsync off), sets the
  viewport by CDP (1600x1000 at dpr 2) and fails a run whose canvas is not 3200x2000 or whose backend is not the one
  asked for (WebGPU; `--webgl` for WebGL 2). Cache off; `--throttle` loads at 80 Mbit/s and 30 ms (DevTools
  emulation, not `throttle_server.py`: compare throttled runs only with throttled runs).
- **Quick (default), one load a city**: usable, first frame, ready, warm-up, the longest task from usable to the
  warm-up's end, MB and requests; at three standard views (overview, street level, a dense area: a small list in the
  script; `--views "A|B|C"` for a single city) the settled frame drawn again `--redraws` times with a fresh shadow map
  (median and max ms, call to GPU done) with draws and triangles from `__viewer.frames()` (never the stats line's
  text: its two lines run together), **moving frames** two ways: a 4 s orbit (the camera set every animation frame) and
  a real 3 s mouse drag through CDP `Input` events (pointer events into the orbit controls: the path a user's drag
  takes), each with fps, median frame ms, draws and triangles, and frames drawn in 3 s of stillness (0); at
  the street view the animating fps and frame ms with waves and traffic on. About 3 min a city, plus the 2 min
  turn-taking gap (`--gap`) between cities.
- **Both backends, and old against new.** New York's WebGL 2 drag got more draws and felt worse while WebGPU-only,
  settled-only checks passed: measure moving frames, and run `--webgl` (the viewer's `?webgl=1`, with `navigator.gpu`
  hidden before the page's scripts for a viewer that lacks the switch) after any change to passes or materials.
  `--ref <folder>` serves a reference copy of a city's web folder (the deployed copy, or an exported older build) beside this tree's and measures it the same way in a Chrome session of its own, the two
  side by side; a viewer without `__viewer.views` takes its views from `tiles/tiles.json`.
- **`--full`** adds the first minute (at usable + 1 s, during the warm-up: orbit, Night, Day, a zoom to the street
  view, the time slider 16 → 22 h, Day; longest task and click-to-screen per step), a second load with
  `?waves=0&traffic=0` for the **layer split** (each menu switch Trees, Rooftops, Markings, Towns, Mirror, Shadows
  clicked off and on at each view: what it adds in settled triangles, draws and ms), and `--idle`.
- **`--idle`**: per view, touch, wait out the 180 s stop, count the frames of the next 10 s (must be 0), and the 30 s
  halving (frame intervals 25-30 s against 30-35 s). ~3.5 min a view; `--idle-fast` uses `__viewer.idle(185)`.
- **Output**: `demos/data/speedtest/run-<date>-<backend>-<mode>.json` (kept, the reference for later runs; written
  after every city, so a partial run survives) and a `.md` beside it: a summary row per city and, per city, every
  metric against the baseline, **worse** / better when it moved over ±10 % and over a small absolute floor (0.5 s,
  2 ms settled, 50 ms for tasks, 1 fps, 0.05 M triangles: run-to-run noise). Exit 1 when a city failed (lost GPU, a
  settled frame with 0 draws, wrong canvas or backend, frames while idle, never ready); `--strict` exits 2 on
  anything worse. A city's numbers mean most against a baseline from the same box, backend and mode.
- **`--wayland`** (a Linux Wayland desktop): launches the plain Chrome binary with `--ozone-platform=wayland` (plain
  Wayland gives WebGPU and WebGL 2 with parallel shader compile; no `sg`/`DISPLAY`, no Vulkan flags) and finds the
  real browser PID; on a tiling window manager it tries to widen the window (a failure is only logged; the viewport is
  set by CDP anyway). The default is X11 through `sg render` with the Vulkan flags (§2, "Linux: getting a real GPU").
- **`--quiet`**: takes the pipeline lock as well as the chrome lock for each city and releases both after (only its
  own), so that no heavy pipeline stage can start under a measurement.
- **The machine rules are built in** (`running-a-build.md` §4, `scripts/lock.sh`): waits while the pipeline lock is held; takes the chrome
  lock per city and releases only its own; ≥ 4 GB available before every load; a fresh Chrome before a second load
  when "shared" > 4000 MB or "available" < 3500 MB; a city aborted under 1.5 GB available; Chrome started through
  `setsid nohup sg render -c "… exec google-chrome …"`, killed by its PID; never `pkill`. Ctrl-C cleans up too.
- **Not covered**: shots (`pixdiff.mjs shoot`, or a city's own shoot script in `eval/`), night views' settled cost
  (only the change of light in `--full`), a CPU-slowed load, per-material costs (the "hide one material at a time"
  method in §6), the GPU process's
  own memory beyond the run's peaks (`peak` in the JSON: lowest available, highest shared, Chrome tree RSS).

### Frame numbers
- The stats line: fps, backend, pixel ratio, triangles, draw calls, what animates, `idle`.
- `renderer.info.render.drawCalls/triangles` after a frame; per module `trees.stats`, `cars.stats`, `rooftops.stats`.
- Compare against a baseline served unchanged in the same browser, in quiet windows (another agent's page on the
  same GPU skews numbers — note it).

### GPU time (WebGL 2: `EXT_disjoint_timer_query_webgl2`)
```js
const v = __viewer, r = v.renderer, gl = r.backend.gl, ext = gl.getExtension('EXT_disjoint_timer_query_webgl2');
const wait = (ms) => new Promise((res) => setTimeout(res, ms));
window.gpuTime = async (fn, n = 8) => {            // median GPU ms of fn() (one warm-up call first)
  const qs = []; fn();
  for (let i = 0; i < n; i++) { const q = gl.createQuery(); gl.beginQuery(ext.TIME_ELAPSED_EXT, q); fn(); gl.endQuery(ext.TIME_ELAPSED_EXT); qs.push(q); await wait(30); }
  const t = [];
  for (const q of qs) { for (let k = 0; k < 200 && !gl.getQueryParameter(q, gl.QUERY_RESULT_AVAILABLE); k++) await wait(10);
    t.push(gl.getQueryParameter(q, gl.QUERY_RESULT) / 1e6); gl.deleteQuery(q); }
  t.sort((a, b) => a - b); return { ms: +t[t.length >> 1].toFixed(1), draws: r.info.render.drawCalls, disjoint: gl.getParameter(ext.GPU_DISJOINT_EXT) };
};
window.bench = async () => {                        // settled vs moving frame of the current view
  v.idle(1000); await wait(300);
  const lights = v.night.state.lights > 0.02, out = {};
  r.setPixelRatio(v.settings.resolution);
  out.settled = await gpuTime(() => (lights ? v.glow.settledGlow : v.pipeline).render());
  r.setPixelRatio(v.settings.movingResolution);
  out.moving = await gpuTime(() => (lights ? v.glow.movingGlow.render() : r.render(v.scene, v.camera)));
  r.setPixelRatio(v.settings.resolution); v.invalidate(); return out;
};
```
On WebGPU, three offers timestamp queries (`new WebGPURenderer({ trackTimestamp: true })`, then
`renderer.resolveTimestampsAsync()`); not used for Shenzhen — verify against the pinned version before relying on it.

### CPU
- `node cdp.mjs profile '<async action>'`: sampled at 0.5 ms; prints top self times (e.g. three's node `build`,
  `analyze`, WebGL `getUniformBlockIndex` → shader building) and total time per viewer function on the stack.
- Long tasks and long animation frames in the page (`PerformanceObserver` on `longtask` and
  `long-animation-frame`, the latter lists the scripts), plus gaps between `requestAnimationFrame` callbacks
  > 100 ms = the main thread was blocked.

### Loading (cold, disabled cache)
Inject a probe before navigation (`Page.addScriptToEvaluateOnNewDocument`) that records: first draw to the page
canvas (wrap `WebGL2RenderingContext.prototype.draw*` and check `FRAMEBUFFER_BINDING === null`), when the loading
panel switches to streaming (view usable), `window.__ready`, `warmLeft() === 0`, rAF gaps, long animation frames,
and `performance.getEntriesByType('resource')` (request count, `transferSize` MB; call
`performance.setResourceTimingBufferSize(100000)` first). Report: first frame, view usable, all loaded, longest stall
after usable / after ready / after warm-up, requests and MB. Run unthrottled and throttled, before and after.

### Failure paths and picture pops (London M9 round 2)
- **Module loading failures**: CDP `Network.setBlockedURLs` (`*vendor/three*`, `*cdn.jsdelivr.net*`, both) before
  navigating, then read the URL the page ended on, the import map and the loading box's text
  (a small CDP script in the city's `eval/`). Also load a fresh git checkout once: a vendored file
  hidden by a `.gitignore` only shows up there.
- **Does a stand-in frame match the frame it replaces?** Take both as page screenshots of the same view (the
  animation stopped with `__viewer.idle(181)` for the settled one, a touch for the other; waves off so the water
  stands still) and diff them: print the mean |diff|, the signed mean (brightness) and the same outside the pixels
  that moved (largest channel difference >= 24).
- **Hide to find**: when a critic names a culprit ("the cars' shadow proxies"), shoot the view with that layer hidden
  and with each material near the target hidden in turn before changing anything: hiding a
  mesh may not stick where the module sets `visible` every frame (cars.js): switch `material.visible` off instead.

### Throttled network
The DevTools presets are mobile; for "home broadband" (80 Mbit/s, 30 ms) serve through a throttling server that
behaves like `http.server` (a connection per request, 2 RTT before the first byte, one shared bandwidth bucket):
```python
# throttle_server.py PORT DIR MBPS RTT_MS
import sys, time, threading, functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
port, root, mbps, rtt = int(sys.argv[1]), sys.argv[2], float(sys.argv[3]), float(sys.argv[4]) / 1000
rate, lock, next_free = mbps * 1e6 / 8, threading.Lock(), [time.monotonic()]
class H(SimpleHTTPRequestHandler):
    def handle_one_request(self):
        time.sleep(2 * rtt); super().handle_one_request()
    def copyfile(self, src, dst):
        while buf := src.read(16384):
            with lock:
                now = time.monotonic(); start = max(now, next_free[0]); next_free[0] = start + len(buf) / rate; wait = next_free[0] - now
            if wait > 0: time.sleep(wait)
            dst.write(buf)
    def log_message(self, *a): pass
class S(ThreadingHTTPServer): request_queue_size = 64
S(('127.0.0.1', port), functools.partial(H, directory=root)).serve_forever()
```

### Tracing shader builds and incomplete frames
Built in since the warm-up fix: `?warmlog=1` keeps `__viewer.warmLog` (each program asked for, linked or compiled
at once with its ms, the warm-up's and a held change of light's rounds, the frames' new pipelines, changes of light,
a lost GPU); save it with the long tasks and the frame log from a measurement script, and line up each long task
with what the log shows inside it. Before limiting compiles on WebGL 2, check
`gl.getExtension('KHR_parallel_shader_compile')` in the browser under test: Chrome with the Vulkan flags has none.
The tools that found the day/night flicker causes. Install from `eval`, trigger the action, restore, return counts:
```js
(async () => {
  const R = __viewer.renderer, nodes = R._nodes, P = R._pipelines;
  const oN = nodes.getForRender.bind(nodes), oP = P.getForRender.bind(P);
  const built = new Map(), pending = new Map();
  const key = (ro) => (ro.material.name || ro.material.type) + '|' + (ro.object.name || ro.object.parent?.name || ro.object.type)
    + (ro.object.isInstancedMesh ? ' inst' : '') + '|ctx' + (R._currentRenderContext?.id ?? '');
  nodes.getForRender = function (ro, ...a) {             // a node material being built now = a shader (re)build
    if (nodes.get(ro).nodeBuilderState === undefined) built.set(key(ro), (built.get(key(ro)) ?? 0) + 1);
    return oN(ro, ...a);
  };
  P.getForRender = function (ro, promises) {             // a pipeline still compiling = the object is left out
    const before = promises ? promises.length : 0, r = oP(ro, promises);
    if (promises && promises.length > before) pending.set(key(ro), (pending.get(key(ro)) ?? 0) + 1);
    return r;
  };
  button('Night'); await new Promise((r) => setTimeout(r, 6000));
  nodes.getForRender = oN; P.getForRender = oP;
  const top = (m) => [...m].sort((a, b) => b[1] - a[1]).slice(0, 25).map(([k, n]) => n + ' ' + k);
  return { built: top(built), pending: top(pending) };
})()
```
- "Built" entries after the warm-up finished = shaders thrown away and rebuilt (here: instanced rooftops/impostors,
  kinds that streamed in later). Also count builds during plain camera moves as a control.
- To find *why* a render object was rebuilt, log its cache-key parts at build time:
  `nodes.getCacheKey(ro.scene, ro.lightsNode)`, `R.contextNode.id/version`, `ro.scene.fogNode?.id`, `ro.id`.
- Per-frame trace: temporarily push `[ms since action, moving ? 'M' : 'S', frameGaps ? 'gap' : 'ok', held ? 'hold' : '-']`
  from `presented()` into a window array; a healthy switch after warm-up reads like `519 M ok hold, 1518 S ok hold`.
- Instrument with a script that replaces an exact snippet (`assert s.count(a) == 1`), and remove it the same way
  before committing (`git diff` must show none of it).

## 6. Before claiming "done"

- Loads with no console errors (`cdp.mjs console`), on WebGL 2 and WebGPU if shaders changed.
- Standard views shot at 2×, compared with the baseline; the user's reported angle reproduced and fixed.
- Idle really idle (stats `idle` within ~0.5 s of stopping, with waves/traffic off or out of view); animation stops
  after `idle(200)`.
- Numbers table (before/after) for anything that could cost: fps or GPU ms, draws, triangles, load times, stalls.
- Test servers and browsers you started are stopped by verified PID; your pages closed; worktrees cleaned.

**Which layer costs a frame: hide one material at a time in the page** (London M9): collect the scene's visible meshes by material, hide each group in turn,
time 3 settled redraws (or 3 s of animating frames) from the frame log, restore. One load, nothing else changes, and
no `?param` that may drop more than it names. The same script counts each request by kind (three.js, the page and
engine modules, data) from the DevTools Network events, to split a load's bytes and time.

**Check the viewport you measured at.** A standalone GPU Chrome's window is clamped to its screen: on a box whose
monitor sleeps under remote login, "1600x1000 at dpr 2" silently became 1280x561 (London M9: every timing at 45 %
of the pixels, found by a critic from the shots' 2560x1122 size). Set it with CDP
`Emulation.setDeviceMetricsOverride {width: 1600, height: 1000, deviceScaleFactor: 2, mobile: false}`, record
`canvas.width x canvas.height` in every perf JSON and fail the run unless it is 3200x2000.

### Exactness of a material swap (Berlin M9 fix round)

Per-pixel shot comparisons need everything else held: three's node time (clouds, wind) frozen in-page
(`renderer._nodes.nodeFrame.update` replaced by one that keeps `time`), waves and traffic off, and the glass probe
not captured again between variants (its capture is not repeatable: two captures of the same view differ by up to 5
levels in the glass). Then repeated shots are bit-identical, and a control variant (the same shot twice) belongs in
every run so the test can be seen to pass for the right reason. Compare a swapped material against the full program
with its branch switched off by a uniform, not only against 0 (see performance-and-loading.md 11).
