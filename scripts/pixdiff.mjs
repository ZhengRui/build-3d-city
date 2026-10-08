// pixdiff.mjs: reference screenshots of every city and a pixel diff against them, the safety net for viewer changes
// that must not change the picture (e.g. a shader refactor that must stay "pixel-identical in every city, day and
// night, WebGPU and WebGL 2"). Node 22+, no dependencies (PNG read and written with node:zlib).
//
//   node pixdiff.mjs shoot   --out <dir> [options]               shoot the standard list into <dir> (PNG + shots.json)
//   node pixdiff.mjs compare <ref dir> <dir> [--diff <dir>]      diff two shot folders (report + diff images)
//   node pixdiff.mjs run     --ref <ref dir> --out <dir> [opts]  shoot this tree into <dir>, then compare with <ref dir>
//
// options: --cities a,b,c (default: the --views-file's cities, else the built-in table's first five)  --views "A|B" (one city)
//          --views-file <file.json> (or CITY3D_VIEWS): {"<city>": ["<overview>", "<street level>", "<dense>", "<landmark>"]}  --times 16,21.5  --webgl
//          --port 8795 | --url http://127.0.0.1:8795/demos/   --cdp-port 9355  --name pixdiff  --per-chrome 2
//          (--times takes 'dusk' too: each city's Dusk preset, files --dusk)
//          --params 'a=1&b=0' (appended to every view's URL: an A/B of viewer switches in one tree)
//          --wayland (a Wayland desktop: the plain Chrome binary, $CHROME_BIN, with --ozone-platform=wayland, as speedtest.mjs)
//          --gap 120  --first (each city's first view only)  --shader (also record the built facade shader of each
//          city's first view, day and night: bytes, lines, declarations, TSL node count; the source to shader--*.txt)
//
// Each view is ONE load: <city>/web/?view=<view>&time=16&waves=0&traffic=0, the background shader warm-up waited for,
// the scene left to stop growing (the settled frame's triangle count stable over three redraws), the menu and the
// stats box hidden, a settled full-resolution frame with nothing left out (__viewer.frames()) redrawn with a fresh
// shadow map: the day shot. Then the time slider is set to 21.5 (the same input path as a drag) and the same wait
// gives the night shot. Waves and traffic off, the clouds held still and the sun's hour fixed: nothing moves between two runs, so two shots
// of one view differ only by GPU noise (measured: see the report's noise floor, references/testing-and-tooling.md).
// 1600 x 1000 CSS px at dpr 2 (Emulation.setDeviceMetricsOverride; the canvas asserted 3200 x 2000).
//
// compare: per view mean |diff| (0-255 per channel, averaged over all pixels and channels), max (largest channel
// difference anywhere), and the share of pixels whose largest channel difference is over 2, 8 and 32 levels; a diff
// image per view (half size, each pixel the largest difference of its 2 x 2 block: the reference dimmed to grey, the
// difference in red, x 8). Writes <dir>/pixdiff.md and pixdiff.json. A view "differs" when over 0.1 % of its pixels
// are more than 8 levels off or its mean is over 0.5 (two runs of the same tree: mean under 0.1, under 0.01 % over 8).
// Exit code 1 when a view differs or is missing.
//
// The machine rules for parallel agents (scripts/lock.sh) are built in as in speedtest.mjs: it waits while the pipeline lock
// is held, takes the chrome lock per Chrome session with the real browser PID and releases only its own, at most
// --per-chrome views (loads) per Chrome, then closes it (fresh profile under <data>/.chrome/, deleted) and waits
// --gap s before the next session; >= 4 GB available before every load; aborts under 1.5 GB. Never pkills.
//
// Paths and Chrome (environment; defaults for a skill at <project>/.agents/skills/build-3d-city, cities in
// <project>/demos/<city>/, data in <project>/demos/data/): CITY3D_TREE (the tree served, default four folders above
// this script), CITY3D_DEMOS (default <tree>/demos), CITY3D_PROJECT (default the tree, or a worktree's main tree),
// CITY3D_DATA (default <project>/demos/data), CITY3D_LOCKS (default <data>/.locks), CITY3D_VIEWS or --views-file
// (a JSON file of each city's standard views, for cities not in the built-in table), CHROME_BIN, CITY3D_DISPLAY,
// CITY3D_XAUTHORITY, CITY3D_CHROME_GROUP, CITY3D_CHROME_EXE: see the comment above `const TREE` for each.
import { spawn, execSync, execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync, symlinkSync } from 'node:fs';
import { dirname, resolve, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { inflateSync, deflateSync } from 'node:zlib';

const argv = process.argv.slice(2);
const has = (k) => argv.includes(`--${k}`);
const val = (k, d) => { const i = argv.indexOf(`--${k}`); return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : d; };
const MODE = argv[0];
if (!['shoot', 'compare', 'run'].includes(MODE) || has('help')) {
  console.log(readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\nimport ')[0]);
  process.exit(MODE ? 0 : 2);
}
const WEBGL = has('webgl');
const WAYLAND = has('wayland');
const NAME = val('name', 'pixdiff');
const PORT = Number(val('port', 8795));
const CDP = Number(val('cdp-port', 9355));
const PER_CHROME = Number(val('per-chrome', 2));
const GAP_S = Number(val('gap', 120));
const TIMES = val('times', '16,21.5').split(',').map((t) => (t === 'dusk' ? t : Number(t)));
const SHADER = has('shader');
const PARAMS = val('params', '');
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

// the standard views per city: overview, street level, a dense area, a landmark (names from tiles.json's views)
const VIEWS = {
  paris: ['Paris overview', "Avenue de l'Opéra (street level)", 'Île de la Cité and the Seine', 'Opéra Garnier'],
  london: ['London overview', 'Ludgate Hill (street level)', 'The City', "St Paul's Cathedral"],
  berlin: ['Berlin overview', 'Unter den Linden (street level)', 'Mitte', 'Karl-Marx-Allee'],
  nyc: ['Manhattan overview', 'Times Square (street level)', 'Midtown', 'Empire State Building'],
  shenzhen: ['Futian CBD', 'Xixiang old town', 'Shenzhen Bay', 'Ping An Finance Center'],
  hongkong: ['Hong Kong overview', 'Nathan Road (street level)', 'Central and Admiralty from the harbour', 'Bank of China Tower'],
  tokyo: ['Ginza and Tsukiji', 'Ginza Chuo-dori (street level)', 'Tokyo overview', 'Tokyo Tower from Shiba Park'],
  singapore: ['Singapore overview', 'Orchard Road (street level)', 'Marina Bay', 'Chinatown (street level)'],
};
Object.assign(VIEWS, EXTRA_VIEWS);   // CITY3D_VIEWS / --views-file: your own cities (or other views of these)
const slug = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const tag = (h) => (h === 'dusk' ? 'dusk' : h >= 19 || h < 5 ? 'night' : 'day');
const fileOf = (city, view, hour) => `${city}--${slug(view)}--${tag(hour)}${TIMES.filter((t) => tag(t) === tag(hour)).length > 1 ? `-${hour}` : ''}.png`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.error(`[${new Date().toTimeString().slice(0, 8)}]`, ...a);
const sh = (cmd) => { try { return execSync(cmd, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }); } catch { return ''; } };
const portBusy = (p) => sh(`ss -ltnH 'sport = :${p}'`).trim() !== '';
const alive = (pid) => { try { process.kill(pid, 0); return true; } catch { return false; } };

// ---------------------------------------------------------------- PNG (8-bit RGB/RGBA, not interlaced: Chrome's screenshots)
export function readPng(file) {
  const b = readFileSync(file);
  let p = 8, w = 0, h = 0, ct = 0;
  const idat = [];
  while (p < b.length) {
    const len = b.readUInt32BE(p), type = b.toString('ascii', p + 4, p + 8), d = b.subarray(p + 8, p + 8 + len);
    if (type === 'IHDR') {
      w = d.readUInt32BE(0); h = d.readUInt32BE(4); ct = d[9];
      if (d[8] !== 8 || d[12] !== 0 || (ct !== 2 && ct !== 6)) throw new Error(`${file}: only 8-bit RGB/RGBA non-interlaced PNGs`);
    } else if (type === 'IDAT') idat.push(d);
    else if (type === 'IEND') break;
    p += 12 + len;
  }
  const bpp = ct === 6 ? 4 : 3, stride = w * bpp, raw = inflateSync(Buffer.concat(idat));
  const out = Buffer.alloc(w * h * 3), prev = Buffer.alloc(stride), cur = Buffer.alloc(stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], row = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let i = 0; i < stride; i++) {
      const a = i >= bpp ? cur[i - bpp] : 0, up = prev[i], c = i >= bpp ? prev[i - bpp] : 0;
      let v = row[i];
      if (f === 1) v += a; else if (f === 2) v += up; else if (f === 3) v += (a + up) >> 1;
      else if (f === 4) { const pp = a + up - c, pa = Math.abs(pp - a), pb = Math.abs(pp - up), pc = Math.abs(pp - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? up : c; }
      cur[i] = v & 255;
    }
    for (let x = 0; x < w; x++) { out[(y * w + x) * 3] = cur[x * bpp]; out[(y * w + x) * 3 + 1] = cur[x * bpp + 1]; out[(y * w + x) * 3 + 2] = cur[x * bpp + 2]; }
    cur.copy(prev);
  }
  return { w, h, rgb: out };
}
const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
const crc = (buf) => { let c = 0xffffffff; for (const x of buf) c = crcTable[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
const chunk = (type, data) => { const l = Buffer.alloc(4); l.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type, 'ascii'), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([l, td, c]); };
export function writePng(file, w, h, rgb) {
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) rgb.copy(raw, y * (w * 3 + 1) + 1, y * w * 3, (y + 1) * w * 3);
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  writeFileSync(file, Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw, { level: 6 })), chunk('IEND', Buffer.alloc(0))]));
}

// ---------------------------------------------------------------- compare
function diffOne(refFile, curFile, diffFile) {
  const a = readPng(refFile), b = readPng(curFile);
  if (a.w !== b.w || a.h !== b.h) return { error: `size ${a.w}x${a.h} vs ${b.w}x${b.h}` };
  const n = a.w * a.h;
  let sum = 0, max = 0, o2 = 0, o8 = 0, o32 = 0, signed = 0;
  const md = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    let m = 0;
    for (let c = 0; c < 3; c++) { const d = b.rgb[i * 3 + c] - a.rgb[i * 3 + c], ad = d < 0 ? -d : d; sum += ad; signed += d; if (ad > m) m = ad; }
    md[i] = m; if (m > max) max = m; if (m > 2) o2++; if (m > 8) o8++; if (m > 32) o32++;
  }
  if (diffFile) {
    const w2 = a.w >> 1, h2 = a.h >> 1, out = Buffer.alloc(w2 * h2 * 3);
    for (let y = 0; y < h2; y++) for (let x = 0; x < w2; x++) {
      let m = 0, g = 0;
      for (let dy = 0; dy < 2; dy++) for (let dx = 0; dx < 2; dx++) {
        const i = (y * 2 + dy) * a.w + x * 2 + dx;
        m = Math.max(m, md[i]); g += a.rgb[i * 3] * 0.3 + a.rgb[i * 3 + 1] * 0.59 + a.rgb[i * 3 + 2] * 0.11;
      }
      const grey = Math.round(g / 4 * 0.35), r = Math.min(255, m * 8), o = (y * w2 + x) * 3;
      out[o] = Math.max(grey, r); out[o + 1] = m ? Math.round(grey * 0.5) : grey; out[o + 2] = m ? Math.round(grey * 0.5) : grey;
    }
    writePng(diffFile, w2, h2, out);
  }
  const pct = (k) => +(100 * k / n).toFixed(3);
  const mean = sum / (n * 3);
  return { mean: +mean.toFixed(3), signed: +(signed / (n * 3)).toFixed(3), max, over2: pct(o2), over8: pct(o8), over32: pct(o32),
    differs: mean > 0.5 || 100 * o8 / n > 0.1 };
}
function compare(refDir, curDir, diffDir = resolve(curDir, 'diff')) {
  mkdirSync(diffDir, { recursive: true });
  const ref = JSON.parse(readFileSync(resolve(refDir, 'shots.json'), 'utf8'));
  const cur = existsSync(resolve(curDir, 'shots.json')) ? JSON.parse(readFileSync(resolve(curDir, 'shots.json'), 'utf8')) : { shots: [] };
  // (the reference's shots this run took (a failed shot is listed too, flagged bad); all of them when it has no shots.json)
  const curFiles = new Set(cur.shots.map((c) => c.file));
  const rows = [];
  for (const s of ref.shots) {
    if (curFiles.size && !curFiles.has(s.file)) continue;
    if (!existsSync(resolve(curDir, s.file))) { rows.push({ file: s.file, missing: true }); continue; }
    const r = diffOne(resolve(refDir, s.file), resolve(curDir, s.file), resolve(diffDir, s.file));
    rows.push({ file: s.file, ...r });
    log(`${s.file}: ${JSON.stringify(r)}`);
  }
  const bad = rows.filter((r) => r.missing || r.error || r.differs);
  const md = [`# pixdiff: ${curDir} against ${refDir}`, '',
    `reference: ${ref.commit ?? '?'} ${ref.backend ?? ''} ${ref.date ?? ''}; this: ${cur.commit ?? '?'} ${cur.backend ?? ''} ${cur.date ?? ''}`, '',
    '| shot | mean | signed | max | % > 2 | % > 8 | % > 32 | |', '|---|--:|--:|--:|--:|--:|--:|---|',
    ...rows.map((r) => r.missing ? `| ${r.file} | | | | | | | MISSING |` : r.error ? `| ${r.file} | | | | | | | ${r.error} |`
      : `| ${r.file} | ${r.mean} | ${r.signed} | ${r.max} | ${r.over2} | ${r.over8} | ${r.over32} | ${r.differs ? 'DIFFERS' : 'same'} |`),
    '', `${rows.length - bad.length} of ${rows.length} the same (mean <= 0.5 and <= 0.1 % of pixels over 8 levels). Diff images: ${diffDir}`];
  writeFileSync(resolve(curDir, 'pixdiff.md'), md.join('\n') + '\n');
  writeFileSync(resolve(curDir, 'pixdiff.json'), JSON.stringify({ ref: refDir, cur: curDir, rows }, null, 1));
  console.log(md.join('\n'));
  return bad.length === 0;
}

// ---------------------------------------------------------------- memory, locks, server, Chrome (as speedtest.mjs)
const freeM = () => { const l = sh('free -m').split('\n').find((x) => x.startsWith('Mem:'))?.split(/\s+/) ?? []; return { availableMB: Number(l[6]), sharedMB: Number(l[4]) }; };
const peak = { minAvailableMB: Infinity, maxSharedMB: 0, maxChromeRssMB: 0 };
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
    if (m.availableMB < 1500 && !lowMemory) { lowMemory = true; log(`available memory ${m.availableMB} MB < 1500: closing Chrome`); killChrome(); }
  }, 3000);
};
const lockSh = (...a) => { try { return { ok: true, out: execFileSync(LOCK_SH, a, { encoding: 'utf8', env: { ...process.env, CITY3D_LOCKS: LOCKS } }).trim() }; } catch (e) { return { ok: false, out: String(e.stdout ?? e.message).trim() }; } };
const lockState = (n) => { try { return readFileSync(resolve(LOCKS, n), 'utf8').trim(); } catch { return 'free'; } };
let holding = false;
const waitPipeline = async () => {
  for (let i = 0; lockState('pipeline') !== 'free'; i++) {
    if (i === 0) log(`pipeline lock held (${lockState('pipeline')}): waiting, retry every 60 s`);
    if (i > 180) throw new Error('pipeline lock held for 3 h');
    await sleep(60000);
  }
};
const takeChrome = async (note) => {
  for (let i = 0; ; i++) {
    await waitPipeline();
    const r = lockSh('take', 'chrome', NAME, note);
    if (r.ok) { holding = true; log(r.out); return; }
    if (i === 0) log(`chrome lock busy (${lockState('chrome')}): waiting, retry every 60 s`);
    if (i > 180) throw new Error('chrome lock busy for 3 h');
    await sleep(60000);
  }
};
const releaseChrome = () => {
  if (!holding) return;
  const cur = lockState('chrome').split(' ');
  if (cur[1] === NAME) log(lockSh('release', 'chrome').out); else log(`chrome lock not ours any more (${cur.join(' ')}): left alone`);
  holding = false;
};
let server = null, serveRoot = null;
const startServer = async (outDir) => {
  if (val('url')) return val('url').replace(/\/?$/, '/');
  if (portBusy(PORT)) throw new Error(`port ${PORT} is busy: pass --url to use a running server, or another --port`);
  serveRoot = resolve(outDir, `.serve-${process.pid}`);
  mkdirSync(serveRoot, { recursive: true });
  symlinkSync(DEMOS, resolve(serveRoot, 'cur'));
  server = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1', '-d', serveRoot], { stdio: 'ignore' });
  for (let i = 0; i < 50 && !portBusy(PORT); i++) await sleep(100);
  log(`server pid ${server.pid} on ${PORT} serving ${DEMOS}`);
  return `http://127.0.0.1:${PORT}/cur/`;
};
const stopServer = () => {
  if (server && alive(server.pid)) { process.kill(server.pid, 'SIGTERM'); log(`server ${server.pid} stopped`); }
  server = null;
  if (serveRoot) { try { rmSync(serveRoot, { recursive: true, force: true }); } catch {} serveRoot = null; }
};
let chrome = null, profileN = 0;
const launchChrome = async (outDir) => {
  if (portBusy(CDP)) throw new Error(`DevTools port ${CDP} busy (an old Chrome?): not starting`);
  mkdirSync(CHROME_DIR, { recursive: true });
  const profile = resolve(CHROME_DIR, `${NAME}-${process.pid}-${++profileN}`);
  const flags = [`--user-data-dir=${profile}`, `--remote-debugging-port=${CDP}`, '--no-first-run', '--no-default-browser-check',
    ...(WAYLAND ? ['--ozone-platform=wayland']
      : ['--enable-unsafe-webgpu', '--enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan', '--use-angle=vulkan']),
    `--window-size=${W},${H}`, 'about:blank'];
  let p;
  // --wayland (as speedtest.mjs): the plain binary on Wayland, no sg wrapper
  if (WAYLAND) p = spawn('setsid', ['nohup', CHROME_BIN, ...flags], { detached: true, stdio: 'ignore' });
  else {
    const cmd = `${X_ENV} exec google-chrome ${flags.join(' ')}`;
    p = X_GROUP ? spawn('setsid', ['nohup', 'sg', X_GROUP, '-c', cmd], { detached: true, stdio: 'ignore' })
      : spawn('setsid', ['nohup', 'sh', '-c', cmd], { detached: true, stdio: 'ignore' });
  }
  p.unref();
  let pid = null;
  for (let i = 0; i < 100 && !pid; i++) {
    await sleep(200);
    pid = Number((WAYLAND
      ? sh(`ps -eo pid=,args= | grep -F -- "--user-data-dir=${profile} " | grep -v -- --type= | grep -v grep | awk '{print $1}'`)
      : sh(`pgrep -f "^${CHROME_EXE} --user-data-dir=${profile}"`)).trim().split('\n')[0]) || null;
  }
  if (!pid) throw new Error('Chrome did not start');
  chrome = { pid, profile };
  writeFileSync(resolve(outDir, `.chrome-${NAME}.pid`), `${pid} ${profile}\n`);
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
};
let pidFile = null;
function killChrome() {
  if (!chrome) return;
  const { pid, profile } = chrome;
  chrome = null;
  clearInterval(memTimer);
  if (alive(pid)) {
    try { process.kill(pid, 'SIGTERM'); } catch {}
    const t = Date.now();
    while (alive(pid) && Date.now() - t < 10000) execSync('sleep 0.2');
    if (alive(pid)) try { process.kill(pid, 'SIGKILL'); } catch {}
  }
  for (let i = 0; i < 25 && portBusy(CDP); i++) execSync('sleep 0.2');
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
  if (pidFile) try { rmSync(pidFile, { force: true }); } catch {}
  log(`chrome ${pid} closed, profile deleted`);
}

class Page {
  async connect() {
    const tabs = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
    this.ws = new WebSocket(tabs.find((t) => t.type === 'page').webSocketDebuggerUrl);
    await new Promise((r, e) => { this.ws.addEventListener('open', r); this.ws.addEventListener('error', e); });
    this.id = 0; this.waiting = new Map(); this.errors = [];
    this.ws.addEventListener('message', (e) => {
      const m = JSON.parse(e.data);
      if (m.id && this.waiting.has(m.id)) { this.waiting.get(m.id)(m); this.waiting.delete(m.id); return; }
      if (m.method === 'Runtime.exceptionThrown') this.errors.push(m.params.exceptionDetails.exception?.description ?? m.params.exceptionDetails.text);
      if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') this.errors.push(m.params.args.map((a) => a.value ?? a.description).join(' '));
    });
    this.ws.addEventListener('close', () => { for (const r of this.waiting.values()) r({ error: { message: 'DevTools connection closed' } }); this.waiting.clear(); });
    await this.send('Page.enable'); await this.send('Runtime.enable'); await this.send('Network.enable');
    await this.send('Network.setCacheDisabled', { cacheDisabled: true });
    await this.send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: DPR, mobile: false });
    await this.send('Emulation.setFocusEmulationEnabled', { enabled: true });
    if (WEBGL) await this.send('Page.addScriptToEvaluateOnNewDocument', { source: `try { Object.defineProperty(Navigator.prototype, 'gpu', { get: () => undefined, configurable: true }); } catch {}` });
    await this.send('Page.bringToFront');
    return this;
  }
  send(method, params = {}) { return new Promise((r) => { const i = ++this.id; this.waiting.set(i, r); this.ws.send(JSON.stringify({ id: i, method, params })); }); }
  async ev(expression) {
    const r = await this.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, timeout: 900000 });
    if (r.error) throw new Error(r.error.message);
    if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description ?? r.result.exceptionDetails.text);
    return r.result?.result?.value;
  }
  call(fn, ...a) { return this.ev(`(${fn.toString()})(...${JSON.stringify(a)})`); }
  async shot(file) {
    const r = await this.send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(file, Buffer.from(r.result.data, 'base64'));
  }
  close() { try { this.ws.close(); } catch {} }
}

// ---------------------------------------------------------------- in-page (each function self-contained)
// wait for the view to be complete and settled; night: the frame must be a night one
async function pageSettle(night) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const t0 = performance.now();
  while (!(window.__ready && window.__viewer) && performance.now() - t0 < 600000) await sleep(250);
  const v = window.__viewer;
  if (!v) return { error: 'no viewer' };
  for (const id of ['menu', 'stats']) { const e = document.getElementById(id); if (e) e.style.display = 'none'; }
  // the sky's clouds still: they drift with the clock (SkyMesh cloudSpeed x time), so two runs of one view differed
  // in the sky by however long each took to settle (facade-ref repeat, 6 Oct: Avenue de l'Opéra mean 3.2, the city 0)
  v.scene.traverse((o) => { if (o.cloudSpeed && 'value' in o.cloudSpeed) o.cloudSpeed.value = 0; });
  const settledAfter = async (t, limit = 60000) => {
    // a settled frame after t, at full resolution, nothing left out, the cover down, finished by the GPU, of the asked light
    for (const ts = performance.now(); performance.now() - ts < limit;) {
      await sleep(100);
      const f = v.frames().filter((x) => x.t > t && x.kind === 'settled' && x.ms !== null && !x.gaps && !x.covered && x.pr === v.settings.resolution && x.night === night).at(-1);
      if (f) return f;
    }
    return null;
  };
  // the background warm-up done (the night's pipelines too, after a change of light)
  while (v.warmLeft() > 0 && performance.now() - t0 < 600000) await sleep(250);
  // the scene stops growing: the settled frame's triangles the same over three redraws 3 s apart
  let last = -1, still = 0, f = null;
  for (let i = 0; still < 3 && i < 60; i++) {
    await sleep(3000);
    while (v.warmLeft() > 0 && performance.now() - t0 < 600000) await sleep(250);
    const t = performance.now();
    v.invalidate({ redraw: true, shadows: true });
    f = await settledAfter(t);
    const n = f?.triangles ?? -2;
    still = n === last ? still + 1 : 0;
    last = n;
  }
  // the frame on screen: drawn again with a fresh shadow map, and 1.5 s of nothing after it
  const t = performance.now();
  v.invalidate({ redraw: true, shadows: true });
  f = await settledAfter(t);
  for (let i = 0; i < 40; i++) { await sleep(250); const l = v.frames().at(-1); if (l && performance.now() - l.t > 1500) break; }
  const cv = v.renderer.domElement;
  return { secs: +((performance.now() - t0) / 1000).toFixed(1), canvas: [cv.width, cv.height], backend: v.renderer.backend.isWebGPUBackend ? 'WebGPU' : 'WebGL 2',
    frame: f ? { draws: f.draws, triangles: f.triangles, ms: Math.round(f.ms), night: f.night } : null, stable: still >= 3, lost: v.lost?.() ?? null };
}
async function pageSetTime(h) {
  const el = document.getElementById('s-time');
  // ('dusk': the city's Dusk preset, city.json time.presets)
  el.value = h === 'dusk' ? window.__viewer.city.time.presets.Dusk : h; el.dispatchEvent(new Event('input'));
  return Number(el.value);
}
// the built facade shader: the code of a building mesh's material as compiled for this backend
async function pageShader() {
  const v = window.__viewer;
  let mesh = null;
  // (after dark the meshes wear the material's lit copy, night.js withLights: same userData)
  v.scene.traverse((o) => { if (!mesh && o.isMesh && o.visible && o.material?.userData === v.mat.buildings.userData) mesh = o; });
  if (!mesh) return { error: 'no facade mesh' };
  const m = mesh.material, seen = new Set();
  const visit = (n) => { if (!n || typeof n !== 'object' || !n.isNode || seen.has(n)) return; seen.add(n); try { for (const c of n.getChildren()) visit(c); } catch {} };
  for (const k of Object.keys(m)) if (k.endsWith('Node') && m[k]?.isNode) visit(m[k]);
  const { fragmentShader: fs, vertexShader: vs } = await v.renderer.debug.getShaderAsync(v.scene, v.camera, mesh);
  // vars: the node builder's own variables (nodeVar<n>, one per node made a variable), a size measure that doesn't count comments
  const stat = (s) => ({ bytes: s.length, lines: s.split('\n').length, vars: new Set(s.match(/\bnodeVar\d+\b/g) ?? []).size });
  return { nodes: seen.size, fragment: stat(fs), vertex: stat(vs), fragmentSource: fs, night: v.night?.state?.on ?? null };
}

// ---------------------------------------------------------------- shoot
async function shoot(outDir) {
  mkdirSync(outDir, { recursive: true });
  pidFile = resolve(outDir, `.chrome-${NAME}.pid`);
  const cities = val('cities', VIEWS_FILE ? Object.keys(EXTRA_VIEWS).join(',') : 'paris,london,berlin,nyc,shenzhen').split(',').map((c) => c.trim().toLowerCase()).filter(Boolean);
  for (const c of cities) if (!VIEWS[c]) throw new Error(`unknown city ${c}: give its views with --views-file or CITY3D_VIEWS`);
  const jobs = cities.flatMap((c) => (val('views') ? val('views').split('|') : has('first') ? VIEWS[c].slice(0, 1) : VIEWS[c]).map((v, i) => ({ city: c, view: v, first: i === 0 })));
  const meta = existsSync(resolve(outDir, 'shots.json')) ? JSON.parse(readFileSync(resolve(outDir, 'shots.json'), 'utf8')) : { shots: [], shaders: {} };
  Object.assign(meta, { commit: gitIn(TREE, 'rev-parse', '--short', 'HEAD'), dirty: !!gitIn(TREE, 'status', '--porcelain'), tree: TREE,
    backend: WEBGL ? 'WebGL 2' : 'WebGPU', date: new Date().toISOString(), times: TIMES, size: [W * DPR, H * DPR] });
  const save = () => writeFileSync(resolve(outDir, 'shots.json'), JSON.stringify(meta, null, 1));
  const base = await startServer(outDir);
  let ok = true;
  try {
    for (let k = 0; k < jobs.length; k += PER_CHROME) {
      if (k > 0) { log(`waiting ${GAP_S} s before the next Chrome session (turn-taking)`); await sleep(GAP_S * 1000); }
      const batch = jobs.slice(k, k + PER_CHROME);
      await takeChrome(`Chrome ${CDP} pixdiff ${batch.map((j) => j.city).join(',')}`);
      try {
        await launchChrome(outDir);
        const page = await new Page().connect();
        for (const job of batch) {
          for (let i = 0; freeM().availableMB < 4000 && i < 60; i++) { if (i === 0) log(`waiting: ${freeM().availableMB} MB available`); await sleep(5000); }
          if (freeM().availableMB < 4000) throw new Error('under 4 GB available');
          await waitPipeline();
          const url = `${base}${job.city}/web/?view=${encodeURIComponent(job.view)}&time=${TIMES[0]}&waves=0&traffic=0${WEBGL ? '&webgl=1' : ''}${PARAMS ? `&${PARAMS}` : ''}`;
          page.errors.length = 0;
          await page.send('Page.navigate', { url });
          await sleep(2000);
          for (const [i, hour] of TIMES.entries()) {
            const setTo = i > 0 ? await page.call(pageSetTime, hour) : hour;
            const st = await page.call(pageSettle, tag(hour) !== 'day');
            const file = fileOf(job.city, job.view, hour);
            const bad = !st || st.error || st.canvas?.[0] !== W * DPR || st.canvas?.[1] !== H * DPR || !st.frame || st.lost
              || st.backend !== (WEBGL ? 'WebGL 2' : 'WebGPU');
            if (bad) ok = false;
            await page.shot(resolve(outDir, file));
            const entry = { file, city: job.city, view: job.view, hour: setTo, url, ...st, errors: page.errors.slice(0, 5), memory: freeM(), bad: !!bad };
            meta.shots = meta.shots.filter((s) => s.file !== file).concat(entry);
            save();
            log(`${file}: ${JSON.stringify({ secs: st?.secs, canvas: st?.canvas, frame: st?.frame, stable: st?.stable, bad: !!bad, errors: entry.errors.length })}`);
            if (SHADER && job.first) {
              const sd = await page.call(pageShader);
              const key = `${job.city}-${tag(hour)}`;
              if (sd.fragmentSource) writeFileSync(resolve(outDir, `shader--${key}--${WEBGL ? 'glsl' : 'wgsl'}.txt`), sd.fragmentSource);
              delete sd.fragmentSource;
              meta.shaders[key] = sd; save();
              log(`shader ${key}: ${JSON.stringify(sd)}`);
            }
          }
          await page.send('Page.navigate', { url: 'about:blank' });
          await sleep(1000);
        }
        page.close();
      } finally {
        killChrome();
        releaseChrome();
      }
    }
  } finally {
    stopServer();
    meta.peak = peak; save();
  }
  log(`peak: ${JSON.stringify(peak)}`);
  return ok;
}

const cleanup = () => { killChrome(); releaseChrome(); stopServer(); };
for (const s of ['SIGINT', 'SIGTERM']) process.on(s, () => { cleanup(); process.exit(130); });
try {
  if (MODE === 'compare') process.exitCode = compare(resolve(argv[1]), resolve(argv[2]), val('diff') && resolve(val('diff'))) ? 0 : 1;
  else {
    const out = resolve(val('out') ?? (() => { throw new Error('--out <dir>'); })());
    const shotOk = await shoot(out);
    if (MODE === 'run') process.exitCode = compare(resolve(val('ref')), out) && shotOk ? 0 : 1;
    else process.exitCode = shotOk ? 0 : 1;
  }
} catch (e) {
  log(`error: ${e.stack ?? e}`);
  cleanup();
  process.exitCode = 3;
}
