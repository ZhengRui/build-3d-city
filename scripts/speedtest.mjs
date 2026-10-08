// speedtest.mjs: one speed test for every city, run after every viewer change so that a fix for one city can't
// quietly slow another. Node 22+, no dependencies. It starts its own static server (optional) and, per city, its
// own GPU Chrome (fresh profile, deleted on close), measures a few standard views, writes one JSON per run and a
// Markdown table, compared with a saved baseline when given one.
//
//   node speedtest.mjs [--cities a,b,c] [--views-file <file.json>] [--quick | --full] [--idle] [--idle-fast]
//                      [--webgl] [--throttle] [--wayland] [--quiet] [--baseline <file.json>] [--save-baseline <file.json>]
//                      [--ref <folder> | --ref nyc=<folder>,... | --ref-url nyc=<url>]
//                      [--views "A|B|C"] [--port 8795 | --url http://127.0.0.1:8795/] [--cdp-port 9355]
//                      [--name speedtest] [--out <dir>] [--redraws 8] [--gap 120] [--strict]
//
// Example: node speedtest.mjs --cities paris,berlin --baseline <data>/speedtest/baseline-webgpu.json
//          node speedtest.mjs --cities nyc --webgl --ref <a deployed copy of demos/nyc/web>     (old against new)
// --cities defaults to the --views-file's cities, else every city in the built-in table (the reference project's).
//
// Per city, one Chrome session (one load; --full: two loads, the second with ?waves=0&traffic=0):
//   load        usable (the loading screen gives way), firstFrame (drawn and the GPU done), ready (window.__ready),
//               warmup (s from usable to the background shader warm-up done), longestTask (ms, the longest
//               main-thread task from usable to the warm-up's end), mb and requests (bytes over the wire to ready)
//               With --throttle the load runs at 80 Mbit/s down, 20 up, 30 ms latency (DevTools emulation).
//   per view    settled: ms from invalidate({redraw, shadows}) to the GPU done, median/min/max of --redraws redraws
//               (each with a fresh shadow map), with draws and triangles from __viewer.frames() (the frame log, not
//               the stats line); moving: fps, median frame ms, draws and triangles of a 4 s orbit (the camera set
//               each animation frame); drag: the same for a real 3 s mouse drag through the page's input path (CDP
//               Input events -> the orbit controls), the moving frames' pixel ratio too; still: frames drawn in 3 s
//               with nothing touched and waves and traffic off (must be 0)
//   animating   at the street view, waves and traffic on (the city's defaults): fps, median frame ms, draws, tris
// --full adds:
//   interaction at usable + 1 s while the warm-up runs (the first minute): a 5 s orbit, Night, Day, a 4 s zoom to
//               the street view, the time slider 16:00 -> 22:00, Day again: per step the longest task, frames, the
//               longest gap between frames, click-to-screen ms for the changes of light
//   layers      the second load (?waves=0&traffic=0): per view the menu switches Trees, Rooftops, Markings, Towns,
//               Mirror, Shadows clicked off one at a time: what each adds in settled triangles, draws and ms
//   idle        per view (as --idle)
// --idle        per view: touch, wait for the animation's 180 s stop (+10 s), count the frames of the next 10 s
//               (must be 0), and the 30 s halving (animating frame intervals 25-30 s and 30-35 s after the touch).
//               About 3.5 min per view. --idle-fast tells the viewer the last input was 185 s ago instead (__viewer.idle).
//
// --webgl      WebGL 2: the viewer's ?webgl=1, and navigator.gpu hidden before the page's scripts (for a viewer
//               without that switch, e.g. an older reference copy)
// --ref        a reference copy of a city's web folder (e.g. the copy last deployed to your static host) served
//               next to this tree's viewer and measured the same way in a Chrome session of its own just before it;
//               the table shows reference against this tree side by side (an older viewer without __viewer.views
//               takes the views from its tiles.json)
// --wayland    a Wayland desktop: launch the plain $CHROME_BIN (default /opt/google/chrome/google-chrome) with
//               --ozone-platform=wayland (no sg, no DISPLAY, no Vulkan flags: plain Wayland gives WebGPU and WebGL 2),
//               find the browser's PID with ps/grep, and on Hyprland widen the tiled window (hyprctl colresize 1.0;
//               a failure, e.g. another compositor, is only logged). Without it: an X11 launch through
//               `sg render` (GPU access for a user outside the render group's login session) with Vulkan flags.
// --quiet      hold the pipeline lock as well as the chrome lock for each city (released together, only ours), so
//               that no heavy pipeline stage can start under a measurement
// A city FAILS (exit code 1) on a lost GPU (__viewer.lost()), a settled frame with 0 draws, a canvas other than
// 3200x2000, a backend other than the one asked for, frames drawn while idle, or a load that never got ready.
// With --baseline, every metric is compared: a change over +-10 % (and over a small absolute floor per metric) is
// "worse" or "better"; --strict exits 2 when anything got worse.
//
// The machine rules for parallel agents (scripts/lock.sh) are built in: it waits while the pipeline lock is held, takes the
// chrome lock per city with the real browser PID and releases only its own, waits --gap s (default 120) before
// retaking it for the next city, checks >= 4 GB available before every load (and restarts Chrome before a second load
// when "shared" > 4000 MB or "available" < 3500 MB), aborts a city when available memory falls under 1.5 GB, starts
// Chrome through `setsid nohup sg render -c "DISPLAY=:0 XAUTHORITY=... exec google-chrome ..."` with the WebGPU flags
// and vsync off, puts its profile under <data>/.chrome/<name>-<n> and deletes it on close, never pkills.
// Output defaults to <data>/speedtest/ (--out; kept: the reference for later runs).
//
// Paths and Chrome (environment; defaults for a skill at <project>/.agents/skills/build-3d-city, cities in
// <project>/demos/<city>/, data in <project>/demos/data/): CITY3D_TREE (the tree served, default four folders above
// this script), CITY3D_DEMOS (default <tree>/demos), CITY3D_PROJECT (default the tree, or a worktree's main tree),
// CITY3D_DATA (default <project>/demos/data), CITY3D_LOCKS (default <data>/.locks), CITY3D_VIEWS or --views-file
// (a JSON file of each city's standard views, for cities not in the built-in table), CHROME_BIN, CITY3D_DISPLAY,
// CITY3D_XAUTHORITY, CITY3D_CHROME_GROUP, CITY3D_CHROME_EXE: see the comment above `const TREE` for each.
import { spawn, execSync, execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------- options
const argv = process.argv.slice(2);
const has = (k) => argv.includes(`--${k}`);
const val = (k, d) => { const i = argv.indexOf(`--${k}`); return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : d; };
if (has('help') || has('h')) { console.log(readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\nimport ')[0]); process.exit(0); }
const FULL = has('full');
const IDLE = FULL || has('idle') || has('idle-fast');
const IDLE_FAST = has('idle-fast');
const WEBGL = has('webgl');
const THROTTLE = has('throttle');
const WAYLAND = has('wayland');
const QUIET = has('quiet');
const STRICT = has('strict');
const NAME = val('name', 'speedtest');
const PORT = Number(val('port', 8795));
const CDP = Number(val('cdp-port', 9355));
const REDRAWS = Number(val('redraws', 8));
const GAP_S = Number(val('gap', 120));
const W = 1600, H = 1000, DPR = 2;

// ---- paths (env overrides; the defaults suit a skill installed at <project>/.agents/skills/build-3d-city):
//   CITY3D_TREE     the tree whose viewer and demos/ are served: default four folders above this script
//   CITY3D_DEMOS    the folder served, holding <city>/web/: default <tree>/demos
//   CITY3D_PROJECT  the project root holding the data: default the tree, or, when the tree is a git worktree, its main tree
//   CITY3D_DATA     default <project>/demos/data;  CITY3D_LOCKS default <data>/.locks (scripts/lock.sh's folder);
//                   Chrome profiles go to <data>/.chrome/ and are deleted on close
//   CITY3D_VIEWS    (or --views-file) a JSON file {"<city>": ["<overview>", "<street level>", "<dense area>", "<landmark>"]}
//                   of view names from each city's city.json `views`, merged over the built-in table below
//   CHROME_BIN      the Chrome binary for --wayland (default /opt/google/chrome/google-chrome); without --wayland Chrome
//                   starts on X11 as `sg $CITY3D_CHROME_GROUP -c "DISPLAY=$CITY3D_DISPLAY XAUTHORITY=$CITY3D_XAUTHORITY
//                   exec google-chrome ..."` (defaults render, :0, /run/user/<uid>/gdm/Xauthority; CITY3D_CHROME_GROUP=""
//                   drops the sg wrapper), found again by CITY3D_CHROME_EXE (default /opt/google/chrome/chrome)
const TREE = resolve(process.env.CITY3D_TREE ?? resolve(dirname(fileURLToPath(import.meta.url)), '../../../..'));
const gitIn = (dir, ...a) => { try { return execFileSync('git', ['-C', dir, ...a], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim(); } catch { return null; } };
const MAIN = resolve(process.env.CITY3D_PROJECT ?? (gitIn(TREE, 'rev-parse', '--show-toplevel') === TREE
  ? dirname(resolve(TREE, gitIn(TREE, 'rev-parse', '--git-common-dir') ?? '.git')) : TREE));   // the project root (locks, data)
const DEMOS = resolve(process.env.CITY3D_DEMOS ?? resolve(TREE, 'demos'));
const DATA = resolve(process.env.CITY3D_DATA ?? resolve(MAIN, 'demos/data'));
const LOCKS = resolve(process.env.CITY3D_LOCKS ?? resolve(DATA, '.locks'));
const LOCK_SH = resolve(dirname(fileURLToPath(import.meta.url)), 'lock.sh');
const CHROME_DIR = resolve(DATA, '.chrome');
const VIEWS_FILE = val('views-file', process.env.CITY3D_VIEWS);
const EXTRA_VIEWS = VIEWS_FILE ? JSON.parse(readFileSync(resolve(VIEWS_FILE), 'utf8')) : {};
const CHROME_BIN = process.env.CHROME_BIN ?? '/opt/google/chrome/google-chrome';
const CHROME_EXE = process.env.CITY3D_CHROME_EXE ?? '/opt/google/chrome/chrome';
const X_GROUP = process.env.CITY3D_CHROME_GROUP ?? 'render';
const X_ENV = `DISPLAY=${process.env.CITY3D_DISPLAY ?? ':0'} XAUTHORITY=${process.env.CITY3D_XAUTHORITY ?? `/run/user/${process.getuid?.() ?? 1000}/gdm/Xauthority`}`;
const OUT = resolve(val('out', resolve(DATA, 'speedtest')));
mkdirSync(OUT, { recursive: true });

// the cities: folder under demos/, and three standard views (from tiles.json's views), the street one animated
const CITIES = {
  paris: { dir: 'paris', views: { overview: 'Paris overview', street: "Avenue de l'Opéra (street level)", dense: 'Île de la Cité and the Seine' } },
  london: { dir: 'london', views: { overview: 'London overview', street: 'Ludgate Hill (street level)', dense: 'The City' } },
  berlin: { dir: 'berlin', views: { overview: 'Berlin overview', street: 'Unter den Linden (street level)', dense: 'Mitte' } },
  nyc: { dir: 'nyc', views: { overview: 'Manhattan overview', street: 'Times Square (street level)', dense: 'Midtown' } },
  // (no street-level preset: its first view, the bay, and the closest area view)
  shenzhen: { dir: 'shenzhen', views: { overview: 'Futian CBD', street: 'Xixiang old town', dense: 'Shenzhen Bay' } },
  singapore: { dir: 'singapore', views: { overview: 'Singapore overview', street: 'Orchard Road (street level)', dense: 'Marina Bay' } },
  hongkong: { dir: 'hongkong', views: { overview: 'Hong Kong overview', street: 'Nathan Road (street level)', dense: 'Central' } },
  tokyo: { dir: 'tokyo', views: { overview: 'Tokyo overview', street: 'Ginza Chuo-dori (street level)', dense: 'Marunouchi and the Imperial Palace' } },
};
// CITY3D_VIEWS / --views-file: your own cities, {"<city>": ["<overview>", "<street level>", "<dense area>", ...]} (the
// file pixdiff.mjs reads) or {"<city>": {"overview": ..., "street": ..., "dense": ...}}; the folder is demos/<city>
for (const [c, v] of Object.entries(EXTRA_VIEWS)) CITIES[c] = { dir: c, views: Array.isArray(v) ? { overview: v[0], street: v[1], dense: v[2] } : v };
const ALIAS = { newyork: 'nyc', 'new-york': 'nyc', ny: 'nyc' };
const cityList = val('cities', (VIEWS_FILE ? Object.keys(EXTRA_VIEWS) : Object.keys(CITIES)).join(',')).split(',').map((c) => ALIAS[c.trim().toLowerCase()] ?? c.trim().toLowerCase()).filter(Boolean);
for (const c of cityList) if (!CITIES[c]) { console.error(`unknown city ${c} (known: ${Object.keys(CITIES).join(', ')})`); process.exit(2); }
// --ref <folder> (one city) or --ref nyc=<folder>,paris=<folder>: a reference copy of the city's web folder (e.g. the
// copy last deployed), measured in a session of its own before this tree's viewer, the
// two side by side in the table. --ref-url city=<url>: the same from a running server (with --url)
const pairs = (s) => Object.fromEntries((s ?? '').split(',').filter(Boolean).map((x) => x.includes('=') ? x.split(/=(.*)/s).slice(0, 2) : [cityList[0], x])
  .map(([c, x]) => [ALIAS[c.toLowerCase()] ?? c.toLowerCase(), x]));
const REF = Object.fromEntries(Object.entries(pairs(val('ref'))).map(([c, x]) => [c, resolve(x)]));
const REF_URL = Object.fromEntries(Object.entries(pairs(val('ref-url'))).map(([c, u]) => [c, u.replace(/\/?$/, '/')]));
if (val('ref') && !val('ref').includes('=') && cityList.length > 1) { console.error('--ref <folder> takes one city; use --ref city=<folder>,...'); process.exit(2); }
for (const [c, d] of Object.entries(REF)) if (!existsSync(resolve(d, 'index.html'))) { console.error(`--ref ${c}: no index.html in ${d}`); process.exit(2); }

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.error(`[${new Date().toTimeString().slice(0, 8)}]`, ...a);
const sh = (cmd) => { try { return execSync(cmd, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }); } catch { return ''; } };
const portBusy = (p) => sh(`ss -ltnH 'sport = :${p}'`).trim() !== '';
const alive = (pid) => { try { process.kill(pid, 0); return true; } catch { return false; } };

// ---------------------------------------------------------------- memory
const peak = { minAvailableMB: Infinity, maxSharedMB: 0, maxChromeRssMB: 0 };
const freeM = () => {
  const l = sh('free -m').split('\n').find((x) => x.startsWith('Mem:'))?.split(/\s+/) ?? [];
  return { availableMB: Number(l[6]), sharedMB: Number(l[4]), usedMB: Number(l[2]) };
};
// the browser's whole process tree (GPU process, renderers, utilities), RSS summed (shared pages counted per process)
const chromeRssMB = (pid) => {
  if (!pid) return 0;
  const kids = new Map(), rss = new Map();
  for (const line of sh('ps -eo pid=,ppid=,rss=').split('\n')) {
    const [p, pp, r] = line.trim().split(/\s+/).map(Number);
    if (!p) continue;
    rss.set(p, r); if (!kids.has(pp)) kids.set(pp, []); kids.get(pp).push(p);
  }
  let kb = 0;
  for (const st = [pid]; st.length;) { const p = st.pop(); kb += rss.get(p) ?? 0; st.push(...(kids.get(p) ?? [])); }
  return Math.round(kb / 1024);
};
let lowMemory = false, memTimer = null;
const watchMemory = (pid) => {
  clearInterval(memTimer);
  memTimer = setInterval(() => {
    const m = freeM();
    peak.minAvailableMB = Math.min(peak.minAvailableMB, m.availableMB);
    peak.maxSharedMB = Math.max(peak.maxSharedMB, m.sharedMB);
    peak.maxChromeRssMB = Math.max(peak.maxChromeRssMB, chromeRssMB(pid));
    if (m.availableMB < 1500 && !lowMemory) { lowMemory = true; log(`available memory ${m.availableMB} MB < 1500: aborting this city`); killChrome(); }
  }, 3000);
};

// ---------------------------------------------------------------- locks (scripts/lock.sh)
const lockSh = (...a) => { try { return { ok: true, out: execFileSync(LOCK_SH, a, { encoding: 'utf8', env: { ...process.env, CITY3D_LOCKS: LOCKS } }).trim() }; } catch (e) { return { ok: false, out: String(e.stdout ?? e.message).trim() }; } };
const lockState = (n) => { try { return readFileSync(resolve(LOCKS, n), 'utf8').trim(); } catch { return 'free'; } };
let holding = false;
const waitPipeline = async () => {
  for (let i = 0; lockState('pipeline') !== 'free'; i++) {
    if (i === 0) log(`pipeline lock held (${lockState('pipeline')}): waiting, retry every 60 s`);
    if (i > 90) throw new Error('pipeline lock held for 90 min');
    await sleep(60000);
  }
};
const takeChrome = async (note) => {
  if (QUIET) return takeBoth(note);
  for (let i = 0; ; i++) {
    await waitPipeline();
    const r = lockSh('take', 'chrome', NAME, note);
    if (r.ok) { holding = true; log(r.out); return; }
    if (i === 0) log(`chrome lock busy (${lockState('chrome')}): waiting, retry every 60 s`);
    if (i > 120) throw new Error('chrome lock busy for 2 h');
    await sleep(60000);
  }
};
// --quiet: the pipeline lock too, so that no heavy stage starts under the measurement (the chrome lock is only
// taken once the pipeline lock is ours; a busy chrome lock gives the pipeline lock back while we wait)
const takeBoth = async (note) => {
  for (let i = 0; ; i++) {
    const p = lockSh('take', 'pipeline', NAME, 'speedtest quiet: ' + note);
    if (p.ok) {
      const r = lockSh('take', 'chrome', NAME, note);
      if (r.ok) { holding = true; log(p.out); log(r.out); return; }
      lockSh('release', 'pipeline');      // (ours: just taken)
      if (i === 0) log(`chrome lock busy (${lockState('chrome')}): waiting, retry every 60 s`);
    } else if (i === 0) log(`pipeline lock held (${lockState('pipeline')}): waiting, retry every 60 s`);
    if (i > 240) throw new Error('locks busy for 4 h');
    await sleep(60000);
  }
};
const releaseChrome = () => {
  if (!holding) return;
  for (const n of QUIET ? ['chrome', 'pipeline'] : ['chrome']) {
    const cur = lockState(n).split(' ');
    // only our own: "<pid|-> <owner> ..." with our name
    if (cur[1] === NAME) log(lockSh('release', n).out); else log(`${n} lock not ours any more (${cur.join(' ')}): left alone`);
  }
  holding = false;
};

// ---------------------------------------------------------------- server
let server = null;
// (one python http.server over a folder of links: cur/ -> this tree's demos/, ref-<city>/ -> a reference copy of a
// city's web folder (--ref); python follows the links. The folder is removed at the end)
let serveRoot = null;
const startServer = async () => {
  if (val('url')) return { cur: val('url').replace(/\/?$/, '/'), ref: (c) => REF_URL[c] };
  if (portBusy(PORT)) throw new Error(`port ${PORT} is busy: pass --url to use a running server, or another --port`);
  serveRoot = resolve(OUT, `.serve-${process.pid}`);
  mkdirSync(serveRoot, { recursive: true });
  symlinkSync(DEMOS, resolve(serveRoot, 'cur'));
  for (const [c, dir] of Object.entries(REF)) symlinkSync(dir, resolve(serveRoot, `ref-${c}`));
  server = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1', '-d', serveRoot], { stdio: 'ignore' });
  for (let i = 0; i < 50 && !portBusy(PORT); i++) await sleep(100);
  const b = `http://127.0.0.1:${PORT}/`;
  log(`server pid ${server.pid} on ${PORT} serving ${DEMOS}${Object.keys(REF).length ? ' and ' + Object.values(REF).join(', ') : ''}`);
  return { cur: `${b}cur/`, ref: (c) => REF[c] ? `${b}ref-${c}/` : null };
};
const stopServer = () => {
  if (server && alive(server.pid)) { process.kill(server.pid, 'SIGTERM'); log(`server ${server.pid} stopped`); }
  server = null;
  if (serveRoot) { try { rmSync(serveRoot, { recursive: true, force: true }); } catch {} serveRoot = null; }    // (the links only)
};

// ---------------------------------------------------------------- chrome
let chrome = null;     // { pid, profile }
let profileN = 0;
const launchChrome = async () => {
  if (portBusy(CDP)) throw new Error(`DevTools port ${CDP} busy (an old Chrome?): not starting`);
  mkdirSync(CHROME_DIR, { recursive: true });
  const profile = resolve(CHROME_DIR, `${NAME}-${process.pid}-${++profileN}`);
  const flags = [`--user-data-dir=${profile}`, `--remote-debugging-port=${CDP}`, '--no-first-run', '--no-default-browser-check',
    ...(WAYLAND ? ['--ozone-platform=wayland']
      : ['--enable-unsafe-webgpu', '--enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan', '--use-angle=vulkan']),
    '--disable-gpu-vsync', '--disable-frame-rate-limit', `--window-size=${W},${H}`, 'about:blank'];
  let p;
  if (WAYLAND) p = spawn('setsid', ['nohup', CHROME_BIN, ...flags], { detached: true, stdio: 'ignore' });
  else {
    const cmd = `${X_ENV} exec google-chrome ${flags.join(' ')}`;
    p = X_GROUP ? spawn('setsid', ['nohup', 'sg', X_GROUP, '-c', cmd], { detached: true, stdio: 'ignore' })
      : spawn('setsid', ['nohup', 'sh', '-c', cmd], { detached: true, stdio: 'ignore' });
  }
  p.unref();
  // the real browser: by its executable and profile (the sg wrapper's command line matches the profile too; on
  // Wayland there is no wrapper: the main process is the one without --type=)
  let pid = null;
  for (let i = 0; i < 100 && !pid; i++) {
    await sleep(200);
    pid = Number((WAYLAND
      ? sh(`ps -eo pid=,args= | grep -F -- "--user-data-dir=${profile} " | grep -v -- --type= | grep -v grep | awk '{print $1}'`)
      : sh(`pgrep -f "^${CHROME_EXE} --user-data-dir=${profile}"`)).trim().split('\n')[0]) || null;
  }
  if (!pid) throw new Error('Chrome did not start');
  chrome = { pid, profile };
  writeFileSync(resolve(OUT, `.chrome-${NAME}.pid`), `${pid} ${profile}\n`);
  if (holding) lockSh('pid', 'chrome', String(pid));
  for (let i = 0; i < 100; i++) { try { await fetch(`http://127.0.0.1:${CDP}/json/version`); break; } catch { await sleep(200); } }
  watchMemory(pid);
  log(`chrome pid ${pid}, profile ${profile}`);
  if (WAYLAND) {
    // widen the tiled window like Super+; (colresize 1.0); failure only logged
    await sleep(1500);
    try {
      const A = execSync(`hyprctl clients -j | python3 -c "import json,sys; print(next(c['address'] for c in json.load(sys.stdin) if c['pid']==${pid}))"`, { encoding: 'utf8' }).trim();
      execSync(`hyprctl dispatch "hl.dsp.focus({ window = \\"address:${A}\\" })"; hyprctl dispatch 'hl.dsp.layout("colresize 1.0")'`, { encoding: 'utf8', stdio: 'ignore', shell: '/bin/bash' });
      log(`window ${A} widened`);
    } catch (e) { log('hyprctl widen failed: ' + e.message.split('\n')[0]); }
  }
  return chrome;
};
function killChrome() {
  if (!chrome) return;
  const { pid, profile } = chrome;
  chrome = null;
  if (alive(pid)) {
    try { process.kill(pid, 'SIGTERM'); } catch {}
    const t = Date.now();
    while (alive(pid) && Date.now() - t < 10000) execSync('sleep 0.2');
    if (alive(pid)) try { process.kill(pid, 'SIGKILL'); } catch {}
  }
  for (let i = 0; i < 25 && portBusy(CDP); i++) execSync('sleep 0.2');
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
  try { rmSync(resolve(OUT, `.chrome-${NAME}.pid`), { force: true }); } catch {}
  log(`chrome ${pid} closed, profile deleted`);
}

// ---------------------------------------------------------------- DevTools
class Page {
  async connect() {
    const tabs = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
    this.ws = new WebSocket(tabs.find((t) => t.type === 'page').webSocketDebuggerUrl);
    await new Promise((r, e) => { this.ws.addEventListener('open', r); this.ws.addEventListener('error', e); });
    this.id = 0; this.waiting = new Map(); this.net = { on: false, bytes: 0, requests: 0 };
    this.ws.addEventListener('message', (e) => {
      const m = JSON.parse(e.data);
      if (m.id && this.waiting.has(m.id)) { this.waiting.get(m.id)(m); this.waiting.delete(m.id); return; }
      if (!this.net.on) return;
      if (m.method === 'Network.requestWillBeSent') this.net.requests++;
      if (m.method === 'Network.loadingFinished') this.net.bytes += m.params.encodedDataLength;
    });
    this.ws.addEventListener('close', () => { for (const r of this.waiting.values()) r({ error: { message: 'DevTools connection closed' } }); this.waiting.clear(); });
    await this.send('Page.enable'); await this.send('Runtime.enable'); await this.send('Network.enable');
    await this.send('Network.setCacheDisabled', { cacheDisabled: true });
    await this.send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: DPR, mobile: false });
    await this.send('Emulation.setFocusEmulationEnabled', { enabled: true });
    return this;
  }
  send(method, params = {}) { return new Promise((r) => { const i = ++this.id; this.waiting.set(i, r); this.ws.send(JSON.stringify({ id: i, method, params })); }); }
  async ev(expression) {
    const r = await this.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, timeout: 900000 });
    if (r.error) throw new Error(r.error.message);
    if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description ?? r.result.exceptionDetails.text);
    return r.result?.result?.value;
  }
  // run a self-contained function in the page with JSON arguments
  call(fn, ...a) { return this.ev(`(${fn.toString()})(...${JSON.stringify(a)})`); }
  close() { try { this.ws.close(); } catch {} }
}

// ---------------------------------------------------------------- in-page code (each function self-contained)
// before the page's own scripts: long tasks and the moment the loading screen gives way, the first frame on screen
const PRELOAD = (WEBGL ? `
  try { Object.defineProperty(Navigator.prototype, 'gpu', { get: () => undefined, configurable: true }); } catch {}` : '') + `
  window.__m = { tasks: [], usable: null };
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__m.tasks.push([e.startTime, e.duration]); })
    .observe({ type: 'longtask', buffered: true });
  const poll = setInterval(() => {
    const el = document.getElementById('loading');
    if ((!el || el.classList.contains('streaming')) && window.__m.usable === null && window.__viewer) window.__m.usable = performance.now();
    if (window.__m.usable !== null && window.__viewer?.drawn?.() > 0 && !window.__m.first) {
      window.__m.first = -1;
      const v = window.__viewer;
      (v.gpuDone ? v.gpuDone() : Promise.resolve()).then(() => { window.__m.first = performance.now(); });
      clearInterval(poll);
    }
  }, 20);`;

async function pageLoad() {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const t0 = performance.now();
  while (!(window.__ready && window.__viewer) && !window.__viewer?.lost?.() && performance.now() - t0 < 600000) await sleep(50);
  while (!(window.__m.first > 0) && !window.__viewer?.lost?.() && performance.now() - t0 < 600000) await sleep(50);
  const nav = performance.getEntriesByType('navigation')[0]?.startTime ?? 0, s = (t) => t && +((t - nav) / 1000).toFixed(2);
  return { usable: s(window.__m.usable), firstFrame: window.__m.first > 0 ? s(window.__m.first) : null, ready: window.__ready ? s(performance.now()) : null,
    lost: window.__viewer?.lost?.() ?? null };
}

async function pageWarm() {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const v = window.__viewer, t0 = performance.now();
  while (v.warmLeft() > 0 && !v.lost?.() && performance.now() - t0 < 300000) await sleep(250);
  await sleep(3000);       // (long-task entries arrive a little later)
  const tasks = window.__m.tasks.filter(([t]) => t > (window.__m.usable ?? 0));
  const cv = v.renderer.domElement;
  return { warmup: +((performance.now() - 3000 - (window.__m.usable ?? t0)) / 1000).toFixed(1),
    longestTask: Math.round(Math.max(0, ...tasks.map(([, d]) => d))),
    canvas: [cv.width, cv.height], backend: v.renderer.backend.isWebGPUBackend ? 'WebGPU' : 'WebGL 2',
    defaults: { waves: v.settings.waves, traffic: v.settings.traffic }, lost: v.lost?.() ?? null };
}

// helpers kept in the page as window.__st
async function pageHelpers(redraws) {
  const v = window.__viewer;
  window.__views = v.views ?? (await (await fetch('tiles/tiles.json')).json()).views;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const raf = () => new Promise((r) => requestAnimationFrame(r));
  const med = (a) => { const s = [...a].filter((x) => x != null).sort((x, y) => x - y); return s.length ? +s[s.length >> 1].toFixed(1) : null; };
  const defaults = { waves: v.settings.waves, traffic: v.settings.traffic };
  const anim = (on) => { v.settings.waves = on && defaults.waves; v.settings.traffic = on && defaults.traffic; v.invalidate(); };
  // until nothing is drawn for 1.5 s and the warm-up has nothing left
  const quiet = async (limit = 60000) => {
    const t = performance.now(); let f = v.drawn(), since = t;
    while (performance.now() - t < limit) {
      await sleep(100);
      if (v.drawn() !== f || v.warmLeft() > 0) { f = v.drawn(); since = performance.now(); } else if (performance.now() - since > 1500) return true;
    }
    return false;
  };
  const M = (x) => x == null ? null : +(x / 1e6).toFixed(3);
  // the settled frame drawn again with a fresh shadow map, n times: call to GPU done
  const settled = async (n = redraws) => {
    const a = [];
    for (let i = 0; i < n; i++) {
      await sleep(300);
      const f0 = v.drawn(), t = performance.now();
      v.invalidate({ redraw: true, shadows: true });
      while (v.drawn() === f0 && performance.now() - t < 10000) await sleep(1);
      await v.gpuDone();
      a.push(performance.now() - t);
    }
    const fr = v.frames().filter((x) => x.kind === 'settled' && !x.covered).slice(-n);
    const last = fr.at(-1);
    return { median: med(a), min: +Math.min(...a).toFixed(1), max: +Math.max(...a).toFixed(1), logged: med(fr.map((f) => f.ms)),
      draws: last?.draws ?? null, triangles: M(last?.triangles) };
  };
  const go = async (name) => {
    const w = window.__views?.find((x) => x.name === name);
    if (!w) return false;
    v.goTo(w); v.invalidate({ shadows: true });
    await sleep(2000); await quiet();
    return true;
  };
  const c = v.camera, tg = v.controls.target;
  // a slow orbit round the target for ms: fps from frames drawn, frame ms, draws and triangles from the log
  const moving = async (ms = 4000) => {
    const r = Math.hypot(c.position.x - tg.x, c.position.z - tg.z), a0 = Math.atan2(c.position.z - tg.z, c.position.x - tg.x);
    const y0 = c.position.y;
    let a = a0;
    const f0 = v.drawn(), t = performance.now();
    while (performance.now() - t < ms) { a += 0.004; c.position.x = tg.x + r * Math.cos(a); c.position.z = tg.z + r * Math.sin(a); c.position.y = y0; v.controls.update(); await raf(); }
    const fps = (v.drawn() - f0) / ((performance.now() - t) / 1000);
    c.position.x = tg.x + r * Math.cos(a0); c.position.z = tg.z + r * Math.sin(a0); c.position.y = y0; v.controls.update();
    await sleep(500);
    const fr = v.frames().filter((f) => f.t >= t && f.kind === 'moving' && f.ms !== null);
    await quiet();
    return { fps: +fps.toFixed(1), ms: med(fr.map((f) => f.ms)), draws: med(fr.map((f) => f.draws)), triangles: M(med(fr.map((f) => f.triangles))) };
  };
  const still = async (ms = 3000) => { const f0 = v.drawn(); await sleep(ms); return v.drawn() - f0; };
  // waves and traffic on (the city's defaults), camera still, after a touch
  const animating = async (ms = 5000) => {
    anim(true); dispatchEvent(new Event('keydown'));
    // (the first animating frames at a view prepare the traffic overlay's shaders and capture it: seconds at
    // Berlin's street view, a frame of 1.7 s; so the count starts once 5 animating frames have come, up to 25 s)
    const tw = performance.now();
    let startS = null;
    while (performance.now() - tw < 25000) {
      await sleep(100);
      const n = v.frames().filter((f) => f.t >= tw && f.kind === 'animating' && f.ms !== null);
      if (n.length >= 5) { startS = +((n[4].t - tw) / 1000).toFixed(2); break; }
      if (performance.now() - tw > 10000 && !n.length && v.animWhy?.()) break;      // (nothing animating here)
    }
    await sleep(500);
    dispatchEvent(new Event('keydown'));
    const f0 = v.drawn(), t = performance.now();
    await sleep(ms);
    const fps = (v.drawn() - f0) / ((performance.now() - t) / 1000);
    await sleep(500);
    const all = v.frames().filter((f) => f.t >= t && f.t <= t + ms);
    const kinds = {};
    for (const f of all) kinds[f.kind] = (kinds[f.kind] ?? 0) + 1;
    const fr = all.filter((f) => f.kind === 'animating' && f.ms !== null);
    let why = v.animWhy?.() || null;
    const state = v.animState?.() ?? null;
    // (a viewer gated on the settled frame (city.json animation.gate not 'frame': New York, Shenzhen) animates only
    // while the last settled frame took <= 150 ms: on a slow GPU nothing animates, which is the viewer's choice)
    if (!fr.length && !why) { const ls = v.frames().filter((f) => f.kind === 'settled' && f.ms !== null).at(-1); if (ls) why = `last settled frame ${Math.round(ls.ms)} ms (the settled gate is 150 ms)`; }
    anim(false); await sleep(500); await quiet();
    return { fps: +fps.toFixed(1), ms: med(fr.map((f) => f.ms)), interval: med(fr.slice(1).map((f, i) => f.t - fr[i].t)), draws: med(fr.map((f) => f.draws)), triangles: M(med(fr.map((f) => f.triangles))),
      startS, kinds, why, state, what: { waves: defaults.waves, traffic: defaults.traffic } };
  };
  window.__st = { v, sleep, quiet, settled, go, moving, still, animating, anim, defaults, med };
  anim(false);
  return defaults;
}

// one view's core numbers
async function pageView(name) {
  const st = window.__st;
  if (!(await st.go(name))) return { missing: true };
  const settled = await st.settled();
  const still = await st.still();
  const moving = await st.moving();
  return { settled, still, moving, lost: st.v.lost?.() ?? null };
}

async function pageAnimating(name) {
  const st = window.__st;
  if (!(await st.go(name))) return { missing: true };
  return st.animating();
}

// what each menu switch adds at a view (the load with ?waves=0&traffic=0): clicked to its other state and back
async function pageLayers(name) {
  const st = window.__st, v = st.v;
  if (!(await st.go(name))) return { missing: true };
  const base = await st.settled(3);
  const out = { base: { ms: base.median, draws: base.draws, triangles: base.triangles } };
  const SW = { Trees: 't-trees', Rooftops: 't-rooftops', Markings: 't-markings', Towns: 't-masses', Mirror: 't-mirror', Shadows: 't-shadows' };
  for (const [label, id] of Object.entries(SW)) {
    const b = document.getElementById(id);
    if (!b || b.hidden) { out[label] = null; continue; }
    const on0 = b.getAttribute('aria-pressed') === 'true';
    b.click(); v.invalidate({ shadows: true });
    await st.sleep(500); await st.quiet();
    const s = await st.settled(3);
    b.click(); v.invalidate({ shadows: true });
    await st.sleep(500); await st.quiet();
    // (what the layer adds: its on state less its off state, whichever it started in)
    const on = on0 ? base : s, off = on0 ? s : base;
    out[label] = { startedOn: on0, triangles: on.triangles != null && off.triangles != null ? +(on.triangles - off.triangles).toFixed(3) : null,
      draws: on.draws != null && off.draws != null ? on.draws - off.draws : null, ms: on.median != null && off.median != null ? +(on.median - off.median).toFixed(1) : null };
  }
  return out;
}

// the first minute: at usable + 1 s, while the background warm-up still runs (Berlin measure.mjs --interact)
async function pageInteract(zoomTo, back) {
  const v = window.__viewer, sleep = (ms) => new Promise((r) => setTimeout(r, ms)), raf = () => new Promise((r) => requestAnimationFrame(r));
  const c = v.camera, tg = v.controls.target, out = { warmLeftAtStart: v.warmLeft(), steps: {} };
  const step = async (name, fn) => {
    const t = performance.now(), f0 = v.drawn(), w0 = v.warmLeft();
    const extra = (await fn()) ?? {};
    const t1 = performance.now();
    await sleep(300);
    const tasks = window.__m.tasks.filter(([s]) => s >= t && s <= t1).map(([, d]) => d);
    const fr = v.frames().filter((f) => f.t >= t && f.t <= t1).map((f) => f.t);
    let gap = fr.length ? fr[0] - t : t1 - t;
    for (let i = 1; i < fr.length; i++) gap = Math.max(gap, fr[i] - fr[i - 1]);
    out.steps[name] = { ms: Math.round(t1 - t), frames: v.drawn() - f0, longestTask: Math.round(Math.max(0, ...tasks)), maxFrameGap: Math.round(gap), warmLeft: [w0, v.warmLeft()], ...extra };
  };
  await step('orbit', async () => {
    const r = Math.hypot(c.position.x - tg.x, c.position.z - tg.z); let a = Math.atan2(c.position.z - tg.z, c.position.x - tg.x);
    const t = performance.now();
    while (performance.now() - t < 5000) { a += 0.004; c.position.x = tg.x + r * Math.cos(a); c.position.z = tg.z + r * Math.sin(a); v.controls.update(); await raf(); }
  });
  const light = async (label) => {
    const btn = [...document.querySelectorAll('#tod button')].find((b) => b.textContent === label), toNight = label === 'Night';
    if (!btn) return { skipped: `no ${label} button` };
    const t = performance.now(); btn.click();
    let first = null;
    while (performance.now() - t < 20000) { first = v.frames().find((f) => f.t >= t && f.night === toNight && !f.covered && !f.gaps && f.ms !== null); if (first) break; await raf(); }
    return { clickToScreen: first ? Math.round(first.t + first.ms - t) : null };
  };
  await sleep(300); await step('night', () => light('Night'));
  await sleep(300); await step('day', () => light('Day'));
  await sleep(300);
  await step('zoom', async () => {
    const p0 = c.position.clone(), t0 = tg.clone();
    const view = (v.views ?? (await (await fetch('tiles/tiles.json')).json()).views)?.find((x) => x.name === zoomTo);
    if (!view) return { skipped: 'no such view' };
    v.goTo(view); const p1 = c.position.clone(), t1 = tg.clone();
    c.position.copy(p0); tg.copy(t0); v.controls.update();
    const o0 = p0.clone().sub(t0), o1 = p1.clone().sub(t1), d0 = o0.length(), d1 = o1.length();
    o0.normalize(); o1.normalize();
    const t = performance.now();
    for (;;) {
      const k = Math.min(1, (performance.now() - t) / 4000), e = k * k * (3 - 2 * k);
      const dir = o0.clone().lerp(o1, e).normalize(), d = d0 * Math.pow(d1 / d0, e);
      tg.lerpVectors(t0, t1, e); c.position.copy(tg).addScaledVector(dir, d); v.controls.update();
      await raf();
      if (k >= 1) break;
    }
    const ts = performance.now(); let s = null;
    while (!s && performance.now() - ts < 20000) { await sleep(20); s = v.frames().find((f) => f.t >= ts && f.kind === 'settled' && f.ms !== null && !f.covered); }
    return { settledAfterMs: s ? Math.round(s.t + s.ms - ts) : null };
  });
  await sleep(300);
  await step('slider', async () => {
    const el = document.getElementById('s-time'); const t = performance.now();
    if (!el) return { skipped: 'no slider' };
    for (;;) { const k = Math.min(1, (performance.now() - t) / 4000); el.value = (16 + 6 * k).toFixed(2); el.dispatchEvent(new Event('input')); await raf(); if (k >= 1) break; }
    const ts = performance.now(); let s = null;
    while (!s && performance.now() - ts < 20000) { await sleep(20); s = v.frames().find((f) => f.t >= ts && f.kind === 'settled' && f.ms !== null && !f.covered && f.night); }
    return { settledAfterMs: s ? Math.round(s.t + s.ms - ts) : null };
  });
  await sleep(300); await step('dayAgain', () => light('Day'));
  out.warmLeftAtEnd = v.warmLeft();
  const bv = (v.views ?? (await (await fetch('tiles/tiles.json')).json()).views)?.find((x) => x.name === back);
  if (bv) v.goTo(bv);
  await sleep(1500);
  out.longestTask = Math.round(Math.max(0, ...Object.values(out.steps).map((s) => s.longestTask)));
  return out;
}

// idle: touch, wait for the animation's stop, count frames in 10 s (Berlin idle.mjs)
async function pageIdle(name, fast) {
  const st = window.__st, v = st.v, sleep = st.sleep;
  if (!(await st.go(name))) return { missing: true };
  st.anim(true);
  dispatchEvent(new Event('keydown'));
  const tTouch = performance.now();
  while (performance.now() - tTouch < 35500) await sleep(100);
  const fr = v.frames().filter((f) => f.kind === 'animating' && f.t >= tTouch + 25000 && f.t <= tTouch + 35000).map((f) => f.t - tTouch);
  const iv = (lo, hi) => { const t = fr.filter((x) => x >= lo && x < hi); return { frames: t.length, medianInterval: st.med(t.slice(1).map((x, i) => x - t[i])) }; };
  const halving = { before: iv(25000, 30000), after: iv(30000, 35000) };
  if (fast) v.idle(185); else while (performance.now() - tTouch < 180000) await sleep(500);
  await sleep(10000);
  const f0 = v.drawn();
  await sleep(10000);
  const drawn = v.drawn() - f0;
  const stats = document.getElementById('stats')?.innerText.replace(/\n/g, ' | ');
  st.anim(false); await st.quiet();
  return { drawn, halving, stats, fast };
}

// ---------------------------------------------------------------- one city
async function loadCity(page, url, preset, extra = '') {
  const free = freeM();
  if (free.availableMB < 4000) throw new Error(`only ${free.availableMB} MB available (< 4000) before the load`);
  const { identifier } = (await page.send('Page.addScriptToEvaluateOnNewDocument', { source: PRELOAD })).result;
  await page.send('Network.emulateNetworkConditions', THROTTLE
    ? { offline: false, latency: 30, downloadThroughput: 80e6 / 8, uploadThroughput: 20e6 / 8 }
    : { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  page.net = { on: true, bytes: 0, requests: 0 };
  const q = new URLSearchParams({ view: preset });
  if (WEBGL) q.set('webgl', '1');
  const full = `${url}?${q}${extra}`;
  await page.send('Page.navigate', { url: full });
  await sleep(1000);
  return { identifier, full };
}
const finishLoad = async (page, identifier) => {
  const load = await page.call(pageLoad);
  page.net.on = false;
  await page.send('Page.removeScriptToEvaluateOnNewDocument', { identifier });
  await page.send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  return { ...load, mb: +(page.net.bytes / 1e6).toFixed(1), requests: page.net.requests };
};
const park = async (page) => { try { await page.send('Page.navigate', { url: 'about:blank' }); await sleep(3000); } catch {} };

// a real drag through the page's input path (pointer events -> the orbit controls): the left button held at the
// canvas's centre and moved 300 px right and back over 3 s; the moving frames' fps, ms, draws, triangles from the log
async function pageMovingSince(t0, t1) {
  const v = window.__viewer, sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  await sleep(500);
  const med = (a) => { const s = [...a].filter((x) => x != null).sort((x, y) => x - y); return s.length ? +s[s.length >> 1].toFixed(1) : null; };
  const all = v.frames().filter((f) => f.t >= t0 && f.t <= t1), fr = all.filter((f) => f.kind === 'moving');
  const kinds = {};
  for (const f of all) kinds[f.kind] = (kinds[f.kind] ?? 0) + 1;
  const done = fr.filter((f) => f.ms !== null);
  const out = { fps: +(all.length / ((t1 - t0) / 1000)).toFixed(1), ms: med(done.map((f) => f.ms)), maxMs: done.length ? Math.round(Math.max(...done.map((f) => f.ms))) : null,
    interval: med(all.slice(1).map((f, i) => f.t - all[i].t)), draws: med(fr.map((f) => f.draws)), triangles: fr.length ? +(med(fr.map((f) => f.triangles)) / 1e6).toFixed(3) : null,
    pr: med(fr.map((f) => f.pr)), kinds };
  await window.__st.quiet();
  return out;
}
async function dragAt(page) {
  const cx = W / 2, cy = H / 2;
  const onCanvas = await page.ev(`[${cx},${cx + 300}].every((x) => document.elementFromPoint(x, ${cy})?.tagName === 'CANVAS')`);
  const t0 = await page.ev('performance.now()');
  const mouse = (type, x) => page.send('Input.dispatchMouseEvent', { type, x, y: cy, button: 'left', buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1 });
  await mouse('mousePressed', cx);
  for (let i = 1; i <= 60; i++) { await mouse('mouseMoved', cx + 300 * Math.sin(Math.PI * i / 60)); await sleep(50); }
  await mouse('mouseReleased', cx);
  const t1 = await page.ev('performance.now()');
  return { onCanvas, ...(await page.call(pageMovingSince, t0, t1)) };
}

async function runCity(key, url, label = 'this tree') {
  const city = CITIES[key];
  const roles = city.views;
  const names = val('views') && cityList.length === 1 ? val('views').split('|') : [roles.overview, roles.street, roles.dense];
  const street = names.includes(roles.street) ? roles.street : names[1] ?? names[0];
  const res = { city: key, url, label, views: {}, failed: [] };
  const fail = (m) => { res.failed.push(m); log(`${key}: FAIL ${m}`); };
  lowMemory = false;
  await takeChrome(`speedtest ${key}${label !== 'this tree' ? ' (reference)' : ''} ${FULL ? 'full' : 'quick'}${WEBGL ? ' webgl' : ''}`);
  let page = null;
  try {
    await launchChrome();
    page = await new Page().connect();
    res.mem = { blank: freeM() };
    // ---- load 1: the city's defaults
    const { identifier, full } = await loadCity(page, url, names[0]);
    res.page = full;
    log(`${key}: loading ${full}`);
    let interactP = null;
    if (FULL) interactP = (async () => {
      const t0 = Date.now();
      while (!(await page.ev('window.__m?.usable ?? null')) && Date.now() - t0 < 600000) await sleep(100);
      await sleep(1000);
      return page.call(pageInteract, street, names[0]);
    })().catch((e) => ({ error: String(e).slice(0, 300) }));
    res.load = await finishLoad(page, identifier);
    res.mem.ready = freeM();
    if (res.load.lost) { fail(`GPU lost during the load (${JSON.stringify(res.load.lost)})`); return res; }
    if (!res.load.ready) { fail('never ready (10 min)'); return res; }
    if (interactP) res.interaction = await interactP;
    const warm = await page.call(pageWarm);
    Object.assign(res.load, { warmup: warm.warmup, longestTask: warm.longestTask });
    Object.assign(res, { canvas: warm.canvas, backend: warm.backend, defaults: warm.defaults });
    log(`${key}: usable ${res.load.usable} s, ready ${res.load.ready} s, ${res.load.mb} MB, warm-up ${warm.warmup} s, longest task ${warm.longestTask} ms, ${warm.backend} ${warm.canvas.join('x')}`);
    if (warm.canvas[0] !== W * DPR || warm.canvas[1] !== H * DPR) fail(`canvas ${warm.canvas.join('x')}, not ${W * DPR}x${H * DPR}`);
    if (warm.backend !== (WEBGL ? 'WebGL 2' : 'WebGPU')) fail(`backend ${warm.backend}, asked for ${WEBGL ? 'WebGL 2' : 'WebGPU'}`);
    if (warm.lost) { fail(`GPU lost (${JSON.stringify(warm.lost)})`); return res; }
    await page.call(pageHelpers, REDRAWS);
    for (const n of names) {
      if (lowMemory) { fail('aborted: low memory'); return res; }
      const r = await page.call(pageView, n);
      const role = Object.entries(roles).find(([, x]) => x === n)?.[0] ?? 'view';
      res.views[n] = { role, ...r };
      if (r.missing) { fail(`no view "${n}"`); continue; }
      if (r.lost) { fail(`GPU lost at ${n}`); return res; }
      if (!(r.settled.draws > 0)) fail(`settled frame at ${n} drew ${r.settled.draws}`);
      r.drag = res.views[n].drag = await dragAt(page);
      log(`${key} / ${n}: settled ${r.settled.median} ms (max ${r.settled.max}), ${r.settled.draws} draws, ${r.settled.triangles} M tris; orbit ${r.moving.fps} fps ${r.moving.ms} ms ${r.moving.draws} draws; drag ${r.drag.fps} fps ${r.drag.ms} ms ${r.drag.draws} draws; still ${r.still}`);
    }
    res.animating = { view: street, ...(await page.call(pageAnimating, street)) };
    log(`${key}: animating at ${street} ${res.animating.fps} fps, ${res.animating.ms} ms`);
    if (IDLE) {
      res.idle = {};
      for (const n of names) {
        if (lowMemory) { fail('aborted: low memory'); return res; }
        log(`${key}: idle at ${n} (${IDLE_FAST ? 'fast' : '~3.5 min'})`);
        const r = res.idle[n] = await page.call(pageIdle, n, IDLE_FAST);
        if (r.drawn > 0) fail(`drew ${r.drawn} frames while idle at ${n}`);
        log(`${key} / ${n}: idle drew ${r.drawn}, halving ${JSON.stringify(r.halving)}`);
      }
    }
    res.mem.end = freeM();
    res.lost = await page.ev('window.__viewer.lost?.() ?? null');
    if (res.lost) fail(`GPU lost (${JSON.stringify(res.lost)})`);
    await park(page);
    res.mem.blankAfter = freeM();
    // ---- load 2 (--full): the layers, waves and traffic off
    if (FULL) {
      const m = freeM();
      if (m.sharedMB > 4000 || m.availableMB < 3500) {
        log(`${key}: shared ${m.sharedMB} MB, available ${m.availableMB} MB: a fresh Chrome for the second load`);
        page.close(); killChrome(); await sleep(3000);
        await launchChrome(); page = await new Page().connect();
      }
      const l2 = await loadCity(page, url, names[0], '&waves=0&traffic=0');
      const ld2 = await finishLoad(page, l2.identifier);
      if (!ld2.ready) { fail('layers load never ready'); return res; }
      await page.call(pageWarm);
      await page.call(pageHelpers, 3);
      res.layers = {};
      for (const n of names) {
        if (lowMemory) { fail('aborted: low memory'); return res; }
        res.layers[n] = await page.call(pageLayers, n);
        log(`${key} / ${n}: layers ${JSON.stringify(res.layers[n])}`);
      }
      const lost = await page.ev('window.__viewer.lost?.() ?? null');
      if (lost) fail(`GPU lost in the layers load (${JSON.stringify(lost)})`);
      await park(page);
    }
  } catch (e) {
    fail(`error: ${String(e.message ?? e).slice(0, 400)}`);
  } finally {
    page?.close();
    killChrome();
    releaseChrome();
  }
  return res;
}

// ---------------------------------------------------------------- comparison
// [key, value, better ('lower'|'higher'), absolute floor below which a change is noise]
function metrics(c) {
  const out = [];
  const add = (k, v, better, floor) => { if (typeof v === 'number' && Number.isFinite(v)) out.push([k, v, better, floor]); };
  if (c.load) {
    add('usable s', c.load.usable, 'lower', 0.5); add('first frame s', c.load.firstFrame, 'lower', 0.5); add('ready s', c.load.ready, 'lower', 1);
    add('warm-up s', c.load.warmup, 'lower', 2); add('longest task ms', c.load.longestTask, 'lower', 50);
    add('download MB', c.load.mb, 'lower', 0.5); add('requests', c.load.requests, 'lower', 5);
  }
  for (const [n, v] of Object.entries(c.views ?? {})) {
    if (v.missing) continue;
    const p = `${n}:`;
    add(`${p} settled ms`, v.settled?.median, 'lower', 2); add(`${p} settled max ms`, v.settled?.max, 'lower', 4);
    add(`${p} draws`, v.settled?.draws, 'lower', 10); add(`${p} triangles M`, v.settled?.triangles, 'lower', 0.05);
    add(`${p} orbit fps`, v.moving?.fps, 'higher', 1); add(`${p} orbit ms`, v.moving?.ms, 'lower', 3);
    add(`${p} orbit draws`, v.moving?.draws, 'lower', 10); add(`${p} orbit triangles M`, v.moving?.triangles, 'lower', 0.05);
    add(`${p} drag fps`, v.drag?.fps, 'higher', 1); add(`${p} drag ms`, v.drag?.ms, 'lower', 3);
    add(`${p} drag draws`, v.drag?.draws, 'lower', 10); add(`${p} drag triangles M`, v.drag?.triangles, 'lower', 0.05);
    add(`${p} still frames`, v.still, 'lower', 0.5);
  }
  if (c.animating && !c.animating.missing) {
    const p = `${c.animating.view}: animating`;
    add(`${p} fps`, c.animating.fps, 'higher', 1); add(`${p} ms`, c.animating.ms, 'lower', 3);
    add(`${p} draws`, c.animating.draws, 'lower', 10); add(`${p} triangles M`, c.animating.triangles, 'lower', 0.05);
  }
  for (const [n, L] of Object.entries(c.layers ?? {})) for (const [k, x] of Object.entries(L ?? {})) {
    if (!x || k === 'base' || k === 'missing') continue;
    add(`${n}: ${k} triangles M`, x.triangles, 'lower', 0.05); add(`${n}: ${k} ms`, x.ms, 'lower', 2);
  }
  for (const [k, s] of Object.entries(c.interaction?.steps ?? {})) {
    add(`first minute ${k} longest task ms`, s.longestTask, 'lower', 50);
    add(`first minute ${k} click-to-screen ms`, s.clickToScreen, 'lower', 50);
    add(`first minute ${k} settled after ms`, s.settledAfterMs, 'lower', 100);
  }
  for (const [n, x] of Object.entries(c.idle ?? {})) add(`${n}: idle frames`, x.drawn, 'lower', 0.5);
  return out;
}
const fmt = (x) => x == null ? '' : Math.abs(x) >= 100 ? String(Math.round(x)) : String(+x.toFixed(2));
function table(c, b, labels = ['Baseline', 'Now']) {
  const lines = [], bm = new Map(b ? metrics(b).map(([k, v]) => [k, v]) : []);
  let worse = 0;
  if (b && b.backend && c.backend && b.backend !== c.backend) lines.push(`(${labels[0]}: ${b.backend}, ${labels[1]}: ${c.backend}: not like for like)`, '');
  lines.push(`| Metric | ${labels[0]} | ${labels[1]} | Change | |`, '|---|---|---|---|---|');
  const seen = new Set();
  for (const [k, v, better, floor] of metrics(c)) {
    seen.add(k);
    const o = bm.get(k);
    let ch = '', st = b ? 'new' : '';
    if (o !== undefined) {
      const d = v - o, rel = o !== 0 ? d / Math.abs(o) : (d === 0 ? 0 : Infinity);
      ch = o !== 0 ? `${d >= 0 ? '+' : ''}${(rel * 100).toFixed(0)} %` : (d === 0 ? '0' : `${d > 0 ? '+' : ''}${fmt(d)}`);
      const big = Math.abs(rel) > 0.10 && Math.abs(d) > floor;
      const isWorse = better === 'lower' ? d > 0 : d < 0;
      st = big ? (isWorse ? '**worse**' : 'better') : 'ok';
      if (big && isWorse) worse++;
    }
    lines.push(`| ${k} | ${o === undefined ? '' : fmt(o)} | ${fmt(v)} | ${ch} | ${st} |`);
  }
  for (const [k, o] of bm) if (!seen.has(k)) lines.push(`| ${k} | ${fmt(o)} |  |  | gone |`);
  lines.push('');
  return { lines, worse };
}
function compare(run, baseline) {
  const lines = [];
  let worse = 0;
  lines.push(`# Speed test ${run.local} (${run.backend}, ${run.mode}${run.throttle ? ', throttled' : ''})`, '');
  lines.push(`Tree ${run.git.branch} ${run.git.commit}${run.git.dirty ? ' (uncommitted changes)' : ''}` + (baseline ? `; baseline ${baseline.local ?? baseline.date} ${baseline.git?.branch ?? ''} ${baseline.git?.commit ?? ''} (${baseline.backend}, ${baseline.mode})` : '; no baseline'), '');
  if (baseline && baseline.mode !== run.mode) lines.push(`(baseline ${baseline.mode}, this run ${run.mode}: --full's first minute runs during the warm-up, so its warm-up and longest task are not comparable with a quick run's)`, '');
  // summary per city (and its reference copy, where measured)
  lines.push('| City | Status | Usable s | Ready s | MB | Longest task ms | Settled ms | Settled draws | Drag fps | Drag ms | Drag draws | Animating fps |', '|---|---|---|---|---|---|---|---|---|---|---|---|');
  const row = (c, name) => {
    const vs = Object.values(c.views ?? {}).filter((v) => !v.missing), j = (f) => vs.map((v) => fmt(f(v))).join(' / ');
    lines.push(`| ${name} | ${c.failed.length ? 'FAILED' : 'ok'} | ${fmt(c.load?.usable)} | ${fmt(c.load?.ready)} | ${fmt(c.load?.mb)} | ${fmt(c.load?.longestTask)} | ${j((v) => v.settled?.median)} | ${j((v) => v.settled?.draws)} | ${j((v) => v.drag?.fps)} | ${j((v) => v.drag?.ms)} | ${j((v) => v.drag?.draws)} | ${fmt(c.animating?.fps)}${c.animating && !c.animating.fps ? ' (no animating frames' + (c.animating.why ? ': ' + c.animating.why : '') + ')' : ''} |`);
  };
  for (const c of Object.values(run.cities)) { if (run.refs?.[c.city]) row(run.refs[c.city], `${c.city} (reference)`); row(c, c.city); }
  lines.push('', 'Per view in the order: overview / street level / dense area (the views are named in each table below).', '');
  for (const c of Object.values(run.cities)) {
    const ref = run.refs?.[c.city];
    if (ref) {
      lines.push(`## ${c.city}: reference ${ref.url} against this tree${ref.failed.length ? ' — reference FAILED: ' + ref.failed.join('; ') : ''}${c.failed.length ? ' — this tree FAILED: ' + c.failed.join('; ') : ''}`, '');
      const t = table(c, ref, ['Reference', 'This tree']);
      lines.push(...t.lines); worse += t.worse;
    }
    if (baseline || !ref) {
      const b = baseline?.cities?.[c.city];
      lines.push(`## ${c.city}${c.failed.length ? ' — FAILED: ' + c.failed.join('; ') : ''}${baseline ? ' (against the baseline)' : ''}`, '');
      const t = table(c, b);
      lines.push(...t.lines); worse += t.worse;
    }
  }
  return { md: lines.join('\n'), worse };
}

// ---------------------------------------------------------------- main
const cleanup = () => { clearInterval(memTimer); killChrome(); releaseChrome(); stopServer(); };
for (const s of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(s, () => { log(`${s}: cleaning up`); cleanup(); process.exit(130); });
process.on('uncaughtException', (e) => { log('uncaught', e); cleanup(); process.exit(1); });

const d0 = new Date(), p2 = (n) => String(n).padStart(2, '0');
const stamp = `${d0.getFullYear()}${p2(d0.getMonth() + 1)}${p2(d0.getDate())}-${p2(d0.getHours())}${p2(d0.getMinutes())}`;      // (local time)
const run = {
  tool: 'speedtest', version: 1, date: d0.toISOString(), local: d0.toLocaleString('sv-SE').slice(0, 16), mode: FULL ? 'full' : 'quick', idle: IDLE ? (IDLE_FAST ? 'fast' : 'real') : false,
  backend: WEBGL ? 'WebGL 2' : 'WebGPU', throttle: THROTTLE, redraws: REDRAWS, viewport: `${W}x${H}@${DPR}`,
  git: { tree: TREE, branch: gitIn(TREE, 'rev-parse', '--abbrev-ref', 'HEAD'), commit: gitIn(TREE, 'rev-parse', '--short', 'HEAD'), dirty: !!gitIn(TREE, 'status', '--porcelain', '--untracked-files=no') },
  host: { cpus: (await import('node:os')).cpus().length, memMB: Math.round((await import('node:os')).totalmem() / 1048576) },
  cities: {},
};
const file = resolve(OUT, `run-${stamp}-${WEBGL ? 'webgl' : 'webgpu'}-${run.mode}.json`);
let base;
try {
  base = await startServer();
  run.server = { url: base.cur, pid: server?.pid ?? null, refs: REF };
  for (let i = 0; i < cityList.length; i++) {
    if (i > 0 && GAP_S > 0) { log(`waiting ${GAP_S} s before retaking the chrome lock (turn-taking)`); await sleep(GAP_S * 1000); }
    const c = cityList[i];
    if (base.ref(c)) {
      run.refs ??= {};
      run.refs[c] = await runCity(c, base.ref(c), `reference ${REF[c] ?? base.ref(c)}`);
      writeFileSync(file, JSON.stringify(run, null, 1));
      if (GAP_S > 0) { log(`waiting ${GAP_S} s before retaking the chrome lock (turn-taking)`); await sleep(GAP_S * 1000); }
    }
    run.cities[c] = await runCity(c, `${base.cur}${CITIES[c].dir}/web/`);
    run.peak = { ...peak, minAvailableMB: peak.minAvailableMB === Infinity ? null : peak.minAvailableMB };
    writeFileSync(file, JSON.stringify(run, null, 1));      // (after every city: a partial run is kept)
  }
} finally {
  cleanup();
}
let baseline = null;
if (val('baseline')) { try { baseline = JSON.parse(readFileSync(resolve(val('baseline')), 'utf8')); } catch (e) { log(`baseline ${val('baseline')}: ${e.message}`); } }
const { md, worse } = compare(run, baseline);
writeFileSync(file.replace(/\.json$/, '.md'), md + '\n');
if (val('save-baseline')) {
  // merged: cities of this run replace theirs, the others are kept
  const bf = resolve(val('save-baseline'));
  let old = null; try { old = JSON.parse(readFileSync(bf, 'utf8')); } catch {}
  const merged = { ...run, cities: { ...(old?.backend === run.backend ? old.cities : {}), ...Object.fromEntries(Object.entries(run.cities).filter(([, c]) => !c.failed.length)) } };
  writeFileSync(bf, JSON.stringify(merged, null, 1));
  log(`baseline saved: ${bf}`);
}
console.log(md);
log(`results: ${file} (+ .md); peak: min available ${run.peak?.minAvailableMB} MB, max shared ${run.peak?.maxSharedMB} MB, Chrome RSS ${run.peak?.maxChromeRssMB} MB`);
const failed = [...Object.values(run.cities), ...Object.values(run.refs ?? {})].some((c) => c.failed.length);
process.exit(failed ? 1 : STRICT && worse ? 2 : 0);
