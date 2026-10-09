// flythrough.mjs: renders a fly-through video of any city from a route file, frame by frame over the DevTools protocol of a
// standalone Chrome, into ffmpeg; with landmark-hint labels (a leader line and a name pill) drawn into the page as a DOM
// overlay before each frame is captured. The specification is references/flythrough-video.md; this is the generic form of
// the New York script (demos/nyc/eval/flythrough.mjs). Node 22+, ffmpeg on the PATH, no other dependencies.
//
//   node flythrough.mjs <route.json> --url http://127.0.0.1:8813/demos/preview/<city>/ [--port 9373] [--fps 30]
//        [--width 1920] [--height 1080] [--preview] [--start S] [--end S] [--out file.mp4] [--labels file.labels.json]
//        [--no-labels] [--dry]
//
// --preview: 5 fps at 960x540 (same path, same timing, the labels scaled with the frame).
// --start/--end: render only that range of the output (a retake); the labels then come from the timeline the last full
//   render wrote (<out>.labels.json, or --labels), so a retake shows them exactly as the whole video does.
// --dry: no frames: load the page, bake the path, print the route summary and the clearance check, and exit.
// The viewer is loaded with ?keeparrays=1 (an opt-in: the tiles' arrays stay in the page) so that the script can build a
// height grid of what is loaded (10 m cells, the highest point in each): it checks the clearance (the guide's rule: no
// structure within 110 m whose top is above the camera) and whether a landmark is hidden behind buildings.
//
// The route file (demos/<city>/eval/film/route.json), scene metres (x east, y up, z south):
//   { "view": "<a preset of the city to load>", "hold": 4,
//     "keys": [{ "p": [x, y, z], "v": 120, "mark": "1 the beat's name", "turn": true, "helix": [x, z], "pb": 0 }, ...],
//     "light": { "day": 16.25, "rampFrom": -30, "split": 0.385, "sunset": 18.5, "end": 18.85 },
//     "end": { "aim": [x, y, z] },
//     "labels": [{ "name": "Eiffel Tower", "short": "330 m · 1889", "x": -3836, "z": 22, "h": 330, "w": 0 }, ...] }
//   v: the speed (m/s) when passing the key, linear in distance between keys (then smoothed); the last key's speed is the
//   speed it comes to rest from, then "hold" seconds at rest. turn: on the keys of a planned turn the yaw-rate cap is
//   40 deg/s instead of 12. helix: the view is turned up to 30 deg (route.helixYaw) towards that point (a spiral round a tower; the
//   heading low-pass is 1 s there). pb: degrees the view is tipped further down at that key. light: the hour stays at
//   "day" until rampFrom (seconds; negative: before the end), eases to "sunset" over the first "split" of the rest, and
//   on to "end". end.aim: the point the view is drawn onto in the last 10 s (held for the last 4). labels: the landmarks
//   that may be named (in priority order); h its height, w its width for a long low one (half the width counts as height).
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(`--${k}`); return i >= 0 ? args[i + 1] : d; };
const flag = (k) => args.includes(`--${k}`);
const VALUED = ['url', 'port', 'fps', 'width', 'height', 'start', 'end', 'out', 'labels'];
const ROUTE_FILE = args.find((a, i) => !a.startsWith('--') && !(i && VALUED.includes(args[i - 1].slice(2))));
if (!ROUTE_FILE) { console.error('usage: node flythrough.mjs <route.json> --url <viewer url> [--port N] [--preview] [--fps N] [--width W] [--height H] [--start S] [--end S] [--out file.mp4] [--labels file] [--no-labels] [--dry]'); process.exit(2); }
const route = JSON.parse(readFileSync(ROUTE_FILE, 'utf8'));
const preview = flag('preview'), DRY = flag('dry'), LABELS_ON = !flag('no-labels') && route.labels?.length;
const PORT = Number(opt('port', process.env.CDP_PORT || 9373));
const BASE = opt('url');
if (!BASE) { console.error('--url <the city viewer> is required'); process.exit(2); }
const FPS = Number(opt('fps', preview ? 5 : 30));
const W = Number(opt('width', preview ? 960 : 1920)), H = Number(opt('height', preview ? 540 : 1080));
if (W % 2 || H % 2) throw new Error('width and height must be even (yuv420p)');
const OUT = resolve(opt('out', `${dirname(resolve(ROUTE_FILE))}/flythrough${preview ? '_preview' : ''}.mp4`));

// ---------------------------------------------------------------- the path
const dist3 = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const lerp3 = (a, b, s) => a.map((v, i) => v + (b[i] - v) * s);
const smoothstep = (s) => { s = Math.min(1, Math.max(0, s)); return s * s * (3 - 2 * s); };
const keys = route.keys.map((k) => ({ ease: 0, pb: 0, ...k }));
// a centripetal Catmull-Rom curve through the keys, sampled about every 2 m
function curve(pts, step = 2) {
  const P = [lerp3(pts[1], pts[0], 2), ...pts, lerp3(pts.at(-2), pts.at(-1), 2)], out = [], keyAt = [];
  for (let i = 1; i < P.length - 2; i++) {
    const [p0, p1, p2, p3] = [P[i - 1], P[i], P[i + 1], P[i + 2]];
    const t1 = Math.sqrt(dist3(p1, p0)) + 1e-6, t2 = t1 + Math.sqrt(dist3(p2, p1)) + 1e-6, t3 = t2 + Math.sqrt(dist3(p3, p2)) + 1e-6;
    const n = Math.max(2, Math.ceil(dist3(p2, p1) / step));
    keyAt.push(out.length);
    for (let k = 0; k < n; k++) {
      const t = t1 + (t2 - t1) * k / n;
      const a1 = lerp3(p0, p1, t / t1), a2 = lerp3(p1, p2, (t - t1) / (t2 - t1)), a3 = lerp3(p2, p3, (t - t2) / (t3 - t2));
      const b1 = lerp3(a1, a2, t / t2), b2 = lerp3(a2, a3, (t - t1) / (t3 - t1));
      out.push(lerp3(b1, b2, (t - t1) / (t2 - t1)));
    }
  }
  keyAt.push(out.length); out.push(pts.at(-1));
  return { pts: out, keyAt };
}
const { pts, keyAt } = curve(keys.map((k) => k.p));
const S = [0];
for (let i = 1; i < pts.length; i++) S.push(S[i - 1] + dist3(pts[i], pts[i - 1]));
// the speed: linear in distance between the keys, then a moving average over 120 m (no kinks at the keys), never under 1 m/s
const vRaw = pts.map((_, i) => { let k = 0; while (k < keys.length - 2 && i > keyAt[k + 1]) k++; const f = (S[i] - S[keyAt[k]]) / Math.max(1e-6, S[keyAt[k + 1]] - S[keyAt[k]]); return keys[k].v + (keys[k + 1].v - keys[k].v) * Math.min(1, f); });
const vS = vRaw.map((_, i) => { let s = 0, c = 0; for (let j = i; j >= 0 && S[i] - S[j] <= 60; j--) { s += vRaw[j]; c++; } for (let j = i + 1; j < pts.length && S[j] - S[i] <= 60; j++) { s += vRaw[j]; c++; } return Math.max(1, s / c); });
// keep the last stretch's slow-down as the keys say (the average would blur the stop)
for (let i = 0; i < pts.length; i++) if (S.at(-1) - S[i] < 60) vS[i] = Math.max(1, Math.min(vS[i], vRaw[i]));
const T = [0];
for (let i = 1; i < pts.length; i++) T.push(T[i - 1] + (S[i] - S[i - 1]) / ((vS[i] + vS[i - 1]) / 2));
const PATH_SECONDS = T.at(-1), HOLD = route.hold ?? 4, ROUTE_SECONDS = PATH_SECONDS + HOLD;
keys.forEach((k, i) => { k.t = T[keyAt[i]]; });
const BEATS = keys.filter((k) => k.mark).map((k, i, a) => ({ name: k.mark, from: k.t, to: a[i + 1]?.t ?? ROUTE_SECONDS }));
const posAt = (t) => {
  if (t >= PATH_SECONDS) return pts.at(-1);
  let lo = 0, hi = T.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (T[m] <= t) lo = m; else hi = m; }
  return lerp3(pts[lo], pts[hi], (t - T[lo]) / Math.max(1e-9, T[hi] - T[lo]));
};
const keyWindows = (pred) => {   // [from, to] times of each run of consecutive keys for which pred holds
  const out = [];
  keys.forEach((k, i) => { if (!pred(k)) return; const prev = out.at(-1); if (prev && prev.last === i - 1) { prev.to = k.t; prev.last = i; } else out.push({ from: keys[Math.max(0, i - 1)].t, to: k.t, last: i, k }); });
  return out.map((w) => ({ ...w, to: keys[Math.min(keys.length - 1, w.last + 1)].t }));
};
const turns = keyWindows((k) => k.turn).map((w) => [w.from, w.to]);
const helices = keyWindows((k) => k.helix).map((w) => ({ win: [w.from, w.to], at: w.k.helix }));
const pitchBias = (t) => { let i = 0; while (i < keys.length - 2 && t > keys[i + 1].t) i++; const a = keys[i], b = keys[i + 1]; return a.pb + (b.pb - a.pb) * smoothstep((t - a.t) / Math.max(1e-6, b.t - a.t)); };

// the light: the city's afternoon until rampFrom, an eased sunset over the first `split` of the rest, then a slow slide on
const L = route.light ?? null;
const hourAt = (t) => {
  if (!L) return null;
  const r0 = L.rampFrom >= 0 ? L.rampFrom : ROUTE_SECONDS + L.rampFrom, r1 = r0 + (ROUTE_SECONDS - r0) * (L.split ?? 5 / 13);
  if (t < r0) return L.day;
  if (t < r1) return L.day + (L.sunset - L.day) * smoothstep((t - r0) / (r1 - r0));
  return L.sunset + (L.end - L.sunset) * smoothstep((t - r1) / Math.max(1e-6, ROUTE_SECONDS - r1));
};

// ---------------------------------------------------------------- the camera (references/flythrough-video.md)
const N = Math.ceil(ROUTE_SECONDS * 30) + 1;
const rawCams = Array.from({ length: N }, (_, i) => posAt(i / 30));
const MIN_CLEAR = 25, WATER_CLEAR = 12, WATER = 0.5, MAX_PITCH_TAN = 0.66;
const LEAD = 2.5, HELIX_YAW = route.helixYaw ?? 30, YAW_WINDOW = 3, PITCH_WINDOW = 2, YAW_RATE = 12, TURN_RATE = 40, AIM = [10, 6];
const AIM_POINT = route.end?.aim;
const rad = Math.PI / 180, wrap = (a) => ((a % 360) + 540) % 360 - 180;
const horiz = (a, b) => Math.hypot(a[0] - b[0], a[2] - b[2]);
const box = (a, r) => a.map((_, i) => { let s = 0, c = 0; for (let j = Math.max(0, i - r); j <= Math.min(a.length - 1, i + r); j++) { s += a[j]; c++; } return s / c; });
const inside = (t, [a, b], soft = 0.5) => smoothstep((t - (a - soft)) / (2 * soft)) * (1 - smoothstep((t - (b - soft)) / (2 * soft)));
function smoothLift(need) {
  const R = 15, win = (a, i) => a.slice(Math.max(0, i - R), i + R + 1);
  const swept = need.map((_, i) => Math.max(...win(need, i)));
  return swept.map((_, i) => { const w = win(swept, i); return w.reduce((a, b) => a + b, 0) / w.length; });
}
const toward = (dir, to, max) => {
  const a = Math.atan2(dir[0] * to[1] - dir[1] * to[0], dir[0] * to[0] + dir[1] * to[1]);
  const r = Math.sign(a) * Math.min(Math.abs(a), max * rad);
  return [dir[0] * Math.cos(r) - dir[1] * Math.sin(r), dir[0] * Math.sin(r) + dir[1] * Math.cos(r)];
};
function lookSeries(path) {
  const n = path.length, last = n - 1, yawOf = (d) => Math.atan2(d[0], -d[1]) / rad;
  const lastMove = (() => { let i = last; while (i > 0 && horiz(path[i], path[last]) < 1) i--; return i; })();   // the hold has no velocity
  const vEnd = path[lastMove].map((v, c) => (v - path[Math.max(0, lastMove - 15)][c]) * 2);
  const yaw = [], D = [], pitch = [], t = (i) => i / 30;
  let hold = null;
  path.forEach((p, i) => {
    const j = Math.min(i + Math.round(LEAD * 30), lastMove);
    const ahead = i + Math.round(LEAD * 30) <= lastMove ? path[j] : path[lastMove].map((v, c) => v + vEnd[c] * (i + LEAD * 30 - lastMove) / 30);
    let dx = ahead[0] - p[0], dz = ahead[2] - p[2];
    const dh = Math.hypot(dx, dz);
    if (dh < 1) { dx = vEnd[0] || 1; dz = vEnd[2]; }
    const y = yawOf([dx, dz]);
    yaw.push(i ? yaw[i - 1] + wrap(y - yaw[i - 1]) : y);
    D.push(Math.min(600, Math.max(150, dh)));
    pitch.push(Math.min(15, Math.max(5, 5 + 10 * (p[1] - 30) / 420)) + pitchBias(t(i)));
    if (AIM_POINT) {
      const w = smoothstep((t(i) - (ROUTE_SECONDS - AIM[0])) / AIM[1]);
      if (w > 0) {
        hold ??= { yaw: yaw[i], pitch: pitch[i] };
        yaw[i] = hold.yaw + w * wrap(yawOf([AIM_POINT[0] - p[0], AIM_POINT[2] - p[2]]) - hold.yaw);
        pitch[i] = hold.pitch + w * (Math.atan2(p[1] - AIM_POINT[1], Math.hypot(AIM_POINT[0] - p[0], AIM_POINT[2] - p[2])) / rad - hold.pitch);
      }
    }
  });
  const smooth = box(yaw, YAW_WINDOW * 15), quick = box(yaw, 15);
  const inHelix = (ti) => Math.max(0, ...helices.map((h) => inside(ti, h.win)));
  const lowPassed = yaw.map((_, i) => smooth[i] + (quick[i] - smooth[i]) * inHelix(t(i)));
  const aimWin = [ROUTE_SECONDS - AIM[0], ROUTE_SECONDS];
  const cap = lowPassed.map((_, i) => Math.max(YAW_RATE, ...turns.map((w) => TURN_RATE * inside(t(i), w)), ...helices.map((h) => TURN_RATE * inside(t(i), h.win)), AIM_POINT ? 30 * inside(t(i), aimWin) : 0) / 30);
  const fwd = [lowPassed[0]];
  for (let i = 1; i < n; i++) fwd.push(fwd[i - 1] + Math.max(-cap[i], Math.min(cap[i], lowPassed[i] - fwd[i - 1])));
  const heading = fwd.slice();
  for (let i = n - 2; i >= 0; i--) heading[i] = heading[i + 1] + Math.max(-cap[i + 1], Math.min(cap[i + 1], fwd[i] - heading[i + 1]));
  const Ds = box(D, YAW_WINDOW * 15), pit = box(pitch, PITCH_WINDOW * 15);
  const looks = path.map((p, i) => {
    let dir = [Math.sin(heading[i] * rad), -Math.cos(heading[i] * rad)];
    for (const h of helices) {
      const bias = HELIX_YAW * inside(t(i), h.win, 2.5), tn = Math.hypot(h.at[0] - p[0], h.at[1] - p[2]);
      if (bias > 0.01) dir = toward(dir, [(h.at[0] - p[0]) / tn, (h.at[1] - p[2]) / tn], bias);
    }
    return [p[0] + dir[0] * Ds[i], p[1] - Math.tan(pit[i] * rad) * Ds[i], p[2] + dir[1] * Ds[i]];
  });
  const rate = heading.map((h, i) => (i ? (h - heading[i - 1]) * 30 : 0));
  return { looks, rate };
}
function bake(ground) {
  const need = rawCams.map((p, i) => ground[i] > WATER ? Math.max(0, ground[i] + MIN_CLEAR - p[1]) : Math.max(0, WATER_CLEAR - p[1]));
  const lift = smoothLift(need);
  const path = rawCams.map((p, i) => [p[0], p[1] + lift[i], p[2]]);
  const { looks: rawLooks, rate } = lookSeries(path);
  const up = smoothLift(rawLooks.map((l, i) => Math.max(0, path[i][1] - MAX_PITCH_TAN * horiz(path[i], l) - l[1])));
  const looks = rawLooks.map((l, i) => [l[0], l[1] + up[i], l[2]]);
  return { path, looks, lift, up, rate };
}
const extreme = (a, from, to, sign) => a.reduce((best, v, i) => i / 30 >= from && i / 30 <= to && v * sign > best.v * sign ? { v, t: i / 30 } : best, { v: -sign * Infinity, t: 0 });

// ---------------------------------------------------------------- the page side: height grid, clearance, labels
// (injected once; __film.grid holds the highest point per 10 m cell of every mesh loaded so far)
const PAGE = String.raw`window.__film = (() => {
  const V = __viewer, cell = 10;
  let G = null;
  const seen = new WeakSet();
  function init(x0, z0, x1, z1) {
    const nx = Math.ceil((x1 - x0) / cell), nz = Math.ceil((z1 - z0) / cell);
    G = { x0, z0, nx, nz, h: new Float32Array(nx * nz).fill(-1e4) };
    return nx * nz;
  }
  function splat() {
    if (!G) return 0;
    let n = 0;
    V.scene.updateMatrixWorld();
    const v = V.camera.position.clone();
    V.scene.traverse((o) => {
      if (!o.isMesh || o.isInstancedMesh || seen.has(o)) return;
      const g = o.geometry, pos = g?.attributes?.position;
      if (!pos || !pos.count || !(pos.array ?? pos.data?.array)?.length) return;
      if (!g.boundingSphere) g.computeBoundingSphere();
      if (g.boundingSphere.radius * o.matrixWorld.getMaxScaleOnAxis() > 6000) return;   // the sky, the sea
      seen.add(o);
      const e = o.matrixWorld.elements;
      for (let i = 0; i < pos.count; i++) {
        const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
        const wx = e[0] * x + e[4] * y + e[8] * z + e[12], wy = e[1] * x + e[5] * y + e[9] * z + e[13], wz = e[2] * x + e[6] * y + e[10] * z + e[14];
        const cx = Math.floor((wx - G.x0) / cell), cz = Math.floor((wz - G.z0) / cell);
        if (cx < 0 || cz < 0 || cx >= G.nx || cz >= G.nz) continue;
        const k = cz * G.nx + cx;
        if (wy > G.h[k]) G.h[k] = wy;
      }
      n++;
    });
    return n;
  }
  const at = (x, z) => { if (!G) return -1e4; const cx = Math.floor((x - G.x0) / cell), cz = Math.floor((z - G.z0) / cell); return cx < 0 || cz < 0 || cx >= G.nx || cz >= G.nz ? -1e4 : G.h[cz * G.nx + cx]; };
  // the guide's rule: nothing within 110 m whose top is above the camera; and the clearance over what is under it
  function clearance([x, y, z], r = 110) {
    let worst = -1e4, wx = 0, wz = 0, under = -1e4;
    for (let dz = -r; dz <= r; dz += cell) for (let dx = -r; dx <= r; dx += cell) {
      const d = Math.hypot(dx, dz); if (d > r) continue;
      const hh = at(x + dx, z + dz);
      if (d <= 15) under = Math.max(under, hh);
      if (hh > worst) { worst = hh; wx = dx; wz = dz; }
    }
    return { above: +(worst - y).toFixed(1), at: [Math.round(x + wx), Math.round(z + wz)], dist: Math.round(Math.hypot(wx, wz)), over: +(y - under).toFixed(1) };
  }
  // a landmark is hidden when fewer than 2 of 3 rays (to its top, 2/3 and 1/3 up) pass over the grid
  function hidden(c, p, skip) {
    const d = Math.hypot(p[0] - c[0], p[1] - c[1], p[2] - c[2]), end = d - skip;
    for (let s = 40; s < end; s += 8) {
      const f = s / d, x = c[0] + (p[0] - c[0]) * f, y = c[1] + (p[1] - c[1]) * f, z = c[2] + (p[2] - c[2]) * f;
      if (at(x, z) > y + 1) return true;
    }
    return false;
  }
  let L = [], css = null, root = null;
  function setLabels(list) {
    L = list.map((l) => ({ ...l, g: V.terrain.height(l.x, l.z), hh: l.h }));
    const k = innerHeight / 1080;
    css ??= document.head.appendChild(document.createElement('style'));
    css.textContent = '#film-labels{position:fixed;inset:0;pointer-events:none;z-index:50;font-family:"Noto Sans","Liberation Sans",sans-serif;color:#fff;-webkit-font-smoothing:antialiased}'
      + '#film-labels .it{position:absolute;inset:0}'
      + '#film-labels .dot{position:absolute;width:' + 10 * k + 'px;height:' + 10 * k + 'px;margin:' + -5 * k + 'px 0 0 ' + -5 * k + 'px;border-radius:50%;background:#fff;box-shadow:0 0 0 ' + 1.5 * k + 'px rgba(0,0,0,.35),0 0 ' + 6 * k + 'px rgba(0,0,0,.35)}'
      + '#film-labels .line{position:absolute;width:' + Math.max(1, 2 * k) + 'px;background:rgba(255,255,255,.9);box-shadow:0 0 ' + 2 * k + 'px rgba(0,0,0,.45)}'
      + '#film-labels .pill{position:absolute;transform:translate(-50%,-100%);white-space:nowrap;padding:' + 8 * k + 'px ' + 20 * k + 'px ' + 10 * k + 'px;border-radius:999px;background:rgba(14,16,20,.52);backdrop-filter:blur(' + 8 * k + 'px) saturate(1.2);border:' + Math.max(1, k) + 'px solid rgba(255,255,255,.28);font-size:' + 26 * k + 'px;font-weight:500;letter-spacing:.01em;line-height:1.15;text-shadow:0 1px 2px rgba(0,0,0,.35)}'
      + '#film-labels .pill.below{transform:translate(-50%,0)}'
      + '#film-labels .pill small{font-weight:400;opacity:.78;margin-left:' + 12 * k + 'px;font-size:' + 20 * k + 'px;letter-spacing:.02em}';
    root ??= document.body.appendChild(Object.assign(document.createElement('div'), { id: 'film-labels' }));
    return L.length;
  }
  // (in front: by the camera-space depth; the NDC z of the reversed-depth projection is no test, a point behind the camera
  // came out 'in front', mirrored into the frame: labels hanging in the sky)
  const proj = (x, y, z) => {
    const v = V.camera.position.clone().set(x, y, z), d = v.clone().applyMatrix4(V.camera.matrixWorldInverse).z, p = v.project(V.camera);
    return { x: (p.x + 1) / 2 * innerWidth, y: (1 - p.y) / 2 * innerHeight, nx: p.x, ny: p.y, front: d < -1 };
  };
  // the dot's point on the landmark's axis: its top, or, when the top is above the frame, where the axis leaves the frame
  // (still on the structure); f: the share of the height
  function anchorOf(l) {
    const t = proj(l.x, l.g + l.hh, l.z);
    if (!t.front || t.ny <= 0.85) return { ...t, f: 1 };
    const b = proj(l.x, l.g, l.z);
    if (!b.front || b.ny > 0.85) return { ...t, f: 1 };
    let lo = 0, hi = 1;
    for (let i = 0; i < 20; i++) { const m = (lo + hi) / 2; if (proj(l.x, l.g + l.hh * m, l.z).ny > 0.85) hi = m; else lo = m; }
    return { ...proj(l.x, l.g + l.hh * lo, l.z), f: lo };
  }
  // per label: on (top on screen, in front), vis (on, big enough, near enough, not hidden)
  function look(wantHidden) {
    V.camera.updateMatrixWorld();
    const c = V.camera.position.toArray();
    return L.map((l, i) => {
      const top = anchorOf(l), base = proj(l.x, l.g, l.z);
      const on = top.front && base.front && Math.abs(top.nx) < 0.92 && top.ny > -0.95 && top.ny < 0.95;
      const size = (proj(l.x, l.g + l.hh, l.z).ny - base.ny) / 2, d = Math.hypot(l.x - c[0], l.z - c[2]);
      const wide = (l.w || 0) / Math.max(1, d) / (2 * Math.tan(V.camera.fov * Math.PI / 360) * V.camera.aspect);   // its width, share of the frame
      const reach = l.reach ?? (l.hh < 100 ? 1600 : l.hh < 250 ? 2200 : 2800);   // (beyond that the haze swallows it)
      // a long low one counts by its width only near and seen from above (its anchor 4 degrees or more below the eye),
      // else its dot sits on the hazy horizon line, not on the thing
      const below = (c[1] - (l.g + l.hh)) / Math.max(1, d) >= 0.1;
      const flat = (l.w || 0) >= 100 && !l.hill;   // (a square, an avenue, a park, a bridge: only near and from above, never by height)
      // (a small one, the Merlion, a gate: allowed at half the size when close)
      let vis = !l.missing && on && d <= reach && (l.hill ? true : flat ? wide >= 0.15 && d <= 1500 && below : size >= 0.045 || (size >= 0.022 && d <= 700));
      const pre = vis;
      if (vis && wantHidden[i] && !((l.w || 0) >= 100 && l.h <= 30)) {   // (a square, a bridge, a park: seen from above, not hidden)
        const skip = Math.max(70, (l.w || 0) / 2 + 25, 0.35 * l.hh);   // (its own structure: a lattice tower's legs spread wide)   // (the landmark's own cells: a tower's legs spread wide)
        const clear = [1, 2 / 3, 1 / 3].map((f) => !hidden(c, [l.x, l.g + l.hh * f * top.f, l.z], skip));
        vis = clear[0] && clear.filter(Boolean).length >= 2;   // the anchor (the top) must be seen
      }
      return { on, vis, pre, core: on && Math.abs(top.nx) < 0.7 && top.ny < 0.92, size: +size.toFixed(3) };
    });
  }
  // draw the labels with these opacities (0..1) and rises (px at 1080)
  function draw(states) {
    const k = innerHeight / 1080, placed = [];
    root.innerHTML = '';
    states.forEach((s, i) => {
      if (!s || s.o <= 0.001) return;
      const l = L[i], t = anchorOf(l);
      if (!t.front) return;
      const lead = 84 * k, below = t.y < 150 * k, el = document.createElement('div');
      el.className = 'it'; el.style.opacity = s.o; el.style.transform = 'translateY(' + (s.rise * k) + 'px)';
      el.innerHTML = '<div class="dot" style="left:' + t.x + 'px;top:' + (t.y - 4 * k) + 'px"></div>'
        + (below ? '<div class="line" style="left:' + (t.x - k) + 'px;top:' + (t.y + 4 * k) + 'px;height:' + lead + 'px"></div><div class="pill below" style="left:' + t.x + 'px;top:' + (t.y + 5 * k + lead) + 'px">'
                 : '<div class="line" style="left:' + (t.x - k) + 'px;top:' + (t.y - 8 * k - lead) + 'px;height:' + lead + 'px"></div><div class="pill" style="left:' + t.x + 'px;top:' + (t.y - 9 * k - lead) + 'px">')
        + l.name + (l.short ? '<small>' + l.short + '</small>' : '') + '</div>';
      root.appendChild(el);
      const pill = el.querySelector('.pill'), r = pill.getBoundingClientRect(), m = 12 * k;   // kept inside the frame
      const dx = r.left < m ? m - r.left : r.right > innerWidth - m ? innerWidth - m - r.right : 0;
      if (dx) pill.style.left = (t.x + dx) + 'px';
      // pills of labels up at once kept 60 px (at 1080) apart: a later one moves up (or down), its leader with it
      const line = el.querySelector('.line');
      for (let n = 0; n < 4; n++) {
        const q = pill.getBoundingClientRect(), g = 60 * k;
        const hit = placed.find((p) => q.left < p.right + g && q.right > p.left - g && q.top < p.bottom + g * 0.4 && q.bottom > p.top - g * 0.4);
        if (!hit) break;
        const shift = below ? hit.bottom + g * 0.4 - q.top : hit.top - g * 0.4 - q.bottom;
        pill.style.top = (parseFloat(pill.style.top) + shift) + 'px';
        if (below) line.style.height = (parseFloat(line.style.height) + shift) + 'px';
        else { line.style.top = (parseFloat(line.style.top) + shift) + 'px'; line.style.height = (parseFloat(line.style.height) - shift) + 'px'; }
      }
      placed.push(pill.getBoundingClientRect());
    });
  }
  // the anchor: the model's own top at the landmark (the highest grid cell within its footprint, not the table's height),
  // or, for a long low one (a square, a bridge, a park, w >= 100 m), the ground; a landmark with nothing modelled there is
  // never labelled (its dot would hang in the air)
  function anchor() {
    return L.map((l) => {
      if (l.hill) { l.hh = 3; return { name: l.name, table: l.h, model: 'summit' }; }   // (a hill: the dot on the ground at its summit)
      const r = Math.min(80, Math.max(20, (l.w || 0) / 2 || 60));
      let top = -1e4;
      for (let dz = -r; dz <= r; dz += cell) for (let dx = -r; dx <= r; dx += cell) if (Math.hypot(dx, dz) <= r) top = Math.max(top, at(l.x + dx, l.z + dz));
      const flat = (l.w || 0) >= 100;
      if (top > l.g + 3 && (flat ? top - l.g <= 2 * l.h + 30 : top - l.g >= Math.min(0.5 * l.h, 25))) l.hh = top - l.g;   // (a tower modelled far lower than its table height is not there: a wrong position)
      else if (flat) l.hh = Math.max(2, Math.min(l.h, top - l.g));
      else l.missing = true;
      return { name: l.name, table: l.h, model: l.missing ? 'none (top ' + Math.round(top - l.g) + ' m)' : Math.round(l.hh) };
    });
  }
  // the label check along the whole path at once (the camera posed, nothing drawn): [[{ on, core, vis }, ...], ...]
  function sweep(poses) {
    const c = V.camera, p0 = c.position.clone(), q0 = c.quaternion.clone(), all = L.map(() => true);
    const out = poses.map(([p, t]) => { c.position.set(...p); c.lookAt(...t); c.updateMatrixWorld(); return look(all).map((r) => (r.on ? 1 : 0) | (r.core ? 2 : 0) | (r.vis ? 4 : 0) | (r.pre ? 8 : 0)); });
    c.position.copy(p0); c.quaternion.copy(q0); c.updateMatrixWorld();
    return out;
  }
  return { init, splat, clearance, setLabels, look, draw, at, sweep, anchor };
})(); true`;

// held 2 to 3 s, out when out of view for 0.3 s (or off the frame), fade out 0.6 s; at most 3 at once, starts 0.8 s apart, in priority order;
// held 2 to 4.5 s, out when out of view for 0.3 s (or off the frame), fade out 0.6 s; at most 2 at once, in priority order;
// none in the first 1.5 s; gone by 3 s before the end
const LB = { settle: 0.5, fadeIn: 0.4, minHold: 2, maxHold: 2.4, lostFor: 0.3, fadeOut: 0.6, noStart: 1.5, endClear: 3, max: 3, gap: 1.0 };
function labelMachine(n) {
  const st = Array.from({ length: n }, () => ({ state: 'idle', since: null, tin: null, tout: null, lastVis: null }));
  const step = (t, looks) => {
    const lastStart = ROUTE_SECONDS - LB.endClear - LB.fadeOut - LB.fadeIn - LB.minHold;
    st.forEach((s, i) => {
      const lk = looks[i];
      if (s.state === 'idle') {
        s.since = lk.vis && lk.core ? (s.since ?? t) : null;   // (a start needs room: the top in the middle 70 %)
        const active = st.filter((x) => x.state === 'on' || x.state === 'out').length;
        const lastIn = Math.max(-Infinity, ...st.filter((x) => x.tin !== null).map((x) => x.tin));
        if (s.since !== null && t - s.since >= LB.settle && t >= LB.noStart && t <= lastStart && active < LB.max && t - lastIn >= LB.gap) { s.state = 'on'; s.tin = t; s.lastVis = t; }
      } else if (s.state === 'on') {
        if (lk.vis) s.lastVis = t;
        const held = t - s.tin;
        if ((!lk.on && held >= LB.fadeIn) || (held >= LB.fadeIn + LB.minHold && t - s.lastVis >= LB.lostFor) || held >= LB.fadeIn + LB.maxHold
          || t >= ROUTE_SECONDS - LB.endClear - LB.fadeOut) { s.state = 'out'; s.tout = t; }
      } else if (s.state === 'out' && t >= s.tout + LB.fadeOut) s.state = 'done';
    });
  };
  return { st, step };
}
// the timeline planned from a sweep along the path (DT s apart): each label in priority order gets the first start where it
// has been clear (vis, top in the middle 70 %) for 0.5 s and stays on the frame for fade-in + the minimum hold, with fewer
// than 3 labels up and no other start within LB.gap s; held up to 3 s while on the frame
function planLabels(flags, DT) {
  const n = flags[0]?.length ?? 0, T = flags.length, ev = Array(n).fill(null), starts = [];
  const lastStart = ROUTE_SECONDS - LB.endClear - LB.fadeOut - LB.fadeIn - LB.minHold;
  const S = Math.round(LB.settle / DT), need = Math.round((LB.fadeIn + LB.minHold) / DT), most = Math.round((LB.fadeIn + LB.maxHold) / DT);
  for (let i = 0; i < n; i++) {
    for (let k = S; k < T; k++) {
      const t = k * DT;
      if (t < LB.noStart || t > lastStart) continue;
      let ok = true;
      for (let j = k - S; j <= k && ok; j++) ok = (flags[j][i] & 4) === 4;
      ok = ok && (flags[k][i] & 2) === 2;   // (clear for 0.5 s, with room in the frame when it starts)
      for (let j = k; j < k + need && ok; j++) ok = j < T && (flags[j][i] & 1) === 1;
      if (!ok) continue;
      let e = k + need; while (e < Math.min(T, k + most) && (flags[e][i] & 1)) e++;
      const tin = t, tout = Math.min(e * DT, ROUTE_SECONDS - LB.endClear - LB.fadeOut);
      if (starts.some((x) => Math.abs(x - tin) < LB.gap)) continue;
      if (ev.filter((x) => x && x.in < tout + LB.fadeOut && tin < x.out + LB.fadeOut).length >= LB.max) continue;
      ev[i] = { in: tin, out: tout }; starts.push(tin); break;
    }
  }
  return ev;
}
const opacityAt = (ev, t) => {   // { in, out } -> { o, rise }
  if (!ev || t < ev.in) return { o: 0, rise: 0 };
  const a = smoothstep((t - ev.in) / LB.fadeIn), b = t >= ev.out ? 1 - smoothstep((t - ev.out) / LB.fadeOut) : 1;
  return { o: a * b, rise: 6 * (1 - a) };
};

// ---------------------------------------------------------------- Chrome over DevTools
let tabs;
try { tabs = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); }
catch (e) { console.error(`no Chrome with a debugging port on ${PORT} (${e.message})`); process.exit(1); }
const page = tabs.find((t) => t.type === 'page');
if (!page) { console.error(`Chrome on port ${PORT} has no page tab`); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r, e) => { ws.addEventListener('open', r); ws.addEventListener('error', () => e(new Error('cannot open the DevTools socket'))); });
let id = 0;
const waiting = new Map(), pageErrors = [];
ws.addEventListener('message', (e) => {
  const m = JSON.parse(e.data);
  if (m.id && waiting.has(m.id)) { const w = waiting.get(m.id); waiting.delete(m.id); m.error ? w.rej(new Error(`${w.method}: ${m.error.message}`)) : w.res(m.result); return; }
  if (m.method === 'Runtime.exceptionThrown') pageErrors.push(m.params.exceptionDetails.exception?.description ?? m.params.exceptionDetails.text);
});
ws.addEventListener('close', () => { for (const w of waiting.values()) w.rej(new Error('the DevTools connection closed')); waiting.clear(); });
const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; waiting.set(i, { res, rej, method }); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, timeout: 600000 });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text);
  return r.result?.value;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------- ffmpeg
let ff = null, ffError = null, ffLog = '', ffDone = Promise.resolve(0);
const feed = (buf) => new Promise((res, rej) => { if (ffError) return rej(ffError); ff.stdin.write(buf, (e) => (e || ffError ? rej(e ?? ffError) : res())); });

const total = Math.round(ROUTE_SECONDS * FPS);
const START = Number(opt('start', 0)), END = Math.min(Number(opt('end', ROUTE_SECONDS)), ROUTE_SECONDS);
const partial = START > 0 || END < ROUTE_SECONDS - 1e-6;
const OUTFILE = partial ? OUT.replace(/\.mp4$/, `_${START}-${END}s.mp4`) : OUT;
const LABEL_FILE = opt('labels', OUT.replace(/\.mp4$/, '.labels.json'));
const REPORT = (partial ? OUTFILE : OUT).replace(/\.mp4$/, '.report.json');
let ok = false, FLAGS = [];
try {
  if (!DRY) { mkdirSync(dirname(OUTFILE), { recursive: true }); startFfmpeg(OUTFILE); }
  await send('Runtime.enable');
  await send('Page.enable');
  // the page must be W x H device pixels. A metrics override in a headful window of another size makes the window jump
  // between the two sizes on every screenshot (it flickers on screen): so size the window instead, so that its viewport
  // times its device pixel ratio is W x H (on a scale-2 Wayland screen: a floating window of W/2 x H/2 logical pixels plus
  // the toolbar; the launcher does that), and the frames are taken as they are. Only a window that is not the right
  // size gets the override (with a warning).
  const inner = async () => evaluate('[innerWidth, innerHeight, devicePixelRatio]');
  let [iw, ih, dpr] = await inner();
  if (Math.round(iw * dpr) !== W || Math.round(ih * dpr) !== H) {
    try {
      const { windowId, bounds } = await send('Browser.getWindowForTarget');
      await send('Browser.setWindowBounds', { windowId, bounds: { width: bounds.width + Math.round(W / dpr) - iw, height: bounds.height + Math.round(H / dpr) - ih } });
      await sleep(500);
      [iw, ih, dpr] = await inner();
    } catch { /* a window manager may refuse */ }
  }
  const OVERRIDE = Math.round(iw * dpr) !== W || Math.round(ih * dpr) !== H;
  if (OVERRIDE) {
    console.log(`WARNING: the page is ${iw}x${ih} at dpr ${dpr}, not ${W}x${H}: emulating it (a visible window then flickers on every screenshot; size the window to the output instead)`);
    await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  } else console.log(`viewport ${iw}x${ih} at dpr ${dpr} = ${W}x${H}: no metrics override`);
  await send('Emulation.setFocusEmulationEnabled', { enabled: true });
  await send('Page.bringToFront');
  const url = `${BASE}${BASE.includes('?') ? '&' : '?'}keeparrays=1${route.view ? `&view=${encodeURIComponent(route.view)}` : ''}`;
  await send('Page.navigate', { url });
  await sleep(1500);
  await evaluate(`(async () => {
    const t0 = performance.now();
    while (!window.__ready && performance.now() - t0 < 600000) await new Promise(r => setTimeout(r, 250));
    if (!window.__ready) throw new Error('the city did not finish loading in 10 minutes');
    if (!window.__viewer?.film) throw new Error('this viewer has no __viewer.film');
    __viewer.film.hide();
    return true;
  })()`);
  await evaluate(PAGE);

  const ground = await evaluate(`${JSON.stringify(rawCams.map((p) => [p[0], p[2]]))}.map(([x, z]) => __viewer.terrain.height(x, z))`);
  const { path, looks, lift, up, rate } = bake(ground);
  const at = (arr, t) => { const f = Math.min(N - 1, Math.max(0, t * 30)), i = Math.min(N - 2, Math.floor(f)); return lerp3(arr[i], arr[i + 1], f - i); };
  const v = path.map((p, i) => (i ? dist3(p, path[i - 1]) * 30 : 0));
  const pitch = path.map((p, i) => Math.atan2(looks[i][1] - p[1], horiz(p, looks[i])) / rad);
  const peak = extreme(v, 0, ROUTE_SECONDS, 1), steep = extreme(pitch, 0, ROUTE_SECONDS, -1);
  const overLand = path.map((p, i) => (ground[i] > WATER ? p[1] - ground[i] : Infinity)), clear = extreme(overLand, 0, ROUTE_SECONDS, -1);
  const overWater = path.map((p, i) => (ground[i] <= WATER ? p[1] : Infinity)), lowW = extreme(overWater, 0, ROUTE_SECONDS, -1);
  const summary = [`route: ${ROUTE_SECONDS.toFixed(1)} s (path ${PATH_SECONDS.toFixed(1)} s + hold ${HOLD} s), ${(S.at(-1) / 1000).toFixed(2)} km`,
    `route: peak ${peak.v.toFixed(0)} m/s at ${peak.t.toFixed(1)} s; steepest pitch ${steep.v.toFixed(1)} deg at ${steep.t.toFixed(1)} s; lowest over land ${clear.v.toFixed(1)} m at ${clear.t.toFixed(1)} s; lowest over water ${lowW.v.toFixed(1)} m at ${lowW.t.toFixed(1)} s; lifted up to ${Math.max(...lift).toFixed(1)} m, look raised up to ${Math.max(...up).toFixed(1)} m`,
    ...BEATS.map((b) => `  beat ${b.name}: ${b.from.toFixed(1)}-${b.to.toFixed(1)} s, peak ${extreme(v, b.from, b.to, 1).v.toFixed(0)} m/s, max yaw rate ${extreme(rate.map(Math.abs), b.from, b.to, 1).v.toFixed(1)} deg/s`)];
  { // the wag check: sign changes of the heading rate where it is above 3 deg/s
    let last = 0, flips = 0, turnsAt = [];
    rate.forEach((r, i) => { if (Math.abs(r) < 3) return; const sg = Math.sign(r); if (last && sg !== last) { flips++; turnsAt.push((i / 30).toFixed(1)); } last = sg; });
    summary.push(`heading: ${flips} sign changes of the yaw rate above 3 deg/s${flips ? ` (at ${turnsAt.join(', ')} s)` : ''}; max ${Math.max(...rate.map(Math.abs)).toFixed(1)} deg/s`);
  }
  summary.forEach((l) => console.log(l));

  // the grid over the route and 3 km round it
  const xs = path.map((p) => p[0]), zs = path.map((p) => p[2]);
  const cells = await evaluate(`__film.init(${Math.min(...xs) - 3000}, ${Math.min(...zs) - 3000}, ${Math.max(...xs) + 3000}, ${Math.max(...zs) + 3000})`);
  if (LABELS_ON) await evaluate(`__film.setLabels(${JSON.stringify(route.labels)})`);
  console.log(`height grid: ${cells} cells of 10 m`);

  const count = Math.max(60, Math.round(ROUTE_SECONDS));
  const samples = Array.from({ length: count }, (_, i) => at(path, (i / (count - 1)) * ROUTE_SECONDS));
  console.log('priming: streaming in what lies along the route, warming shaders');
  await evaluate(`__viewer.film.prime(${JSON.stringify(samples)}).then(() => true)`);
  console.log(`grid: ${await evaluate('__film.splat()')} meshes`);

  // ---------------------------------------------------------------- the frames
  const from = Math.round(START * FPS), to = Math.min(total, Math.round(END * FPS));
  let timeline = null;
  if (LABELS_ON && partial) {
    if (existsSync(LABEL_FILE)) timeline = JSON.parse(readFileSync(LABEL_FILE, 'utf8')).labels;
    else console.log(`no ${LABEL_FILE} (from a full render): this retake has no labels`);
  }
  if (LABELS_ON && !partial) {   // the plan: a sweep along the path, 0.2 s apart
    const DT = 0.2, poses = [];
    for (let t = 0; t <= ROUTE_SECONDS; t += DT) poses.push([at(path, t), at(looks, t)]);
    const anchors = await evaluate('__film.anchor()');
    console.log(`label anchors (table -> model height): ${anchors.map((a) => `${a.name} ${a.table}->${a.model ?? 'none'}`).join('; ')}`);
    const flags = await evaluate(`__film.sweep(${JSON.stringify(poses)})`);
    FLAGS = flags;
    timeline = planLabels(flags, DT);
    writeFileSync(LABEL_FILE, JSON.stringify({ route: ROUTE_FILE, labels: timeline }, null, 1));
  }
  const machine = null;
  const clearLog = [], report = { summary, clearance: [], labels: null };
  const stepFrames = DRY ? Math.max(1, Math.round(FPS)) : 1;
  console.log(DRY ? 'dry run: the clearance check once a second, no frames' : `rendering frames ${from}..${to - 1} of ${total} (${W}x${H}, ${FPS} fps) to ${OUTFILE}`);
  const t0 = Date.now();
  for (let i = from; i < to; i += stepFrames) {
    const t = i / FPS, hour = hourAt(t);
    const spec = { position: at(path, t), target: at(looks, t), ...(hour === null ? {} : { hour }) };
    await evaluate(`__viewer.film.setClock(${t}); __viewer.film.frame(${JSON.stringify(spec)}).then(() => true)`);
    if (i % Math.max(1, Math.round(FPS)) === 0 || DRY) {   // once a second: the newly loaded meshes into the grid, the clearance
      await evaluate('__film.splat()');
      const c = await evaluate(`__film.clearance(${JSON.stringify(spec.position)})`);
      clearLog.push({ t: +t.toFixed(1), y: Math.round(spec.position[1]), ...c });
      if (c.above > 0 && c.dist > 0) console.log(`  clearance: at ${t.toFixed(1)} s something ${c.above} m above the camera ${c.dist} m off (at ${c.at})`);
    }
    if (LABELS_ON && (machine || !DRY)) {
      let states;
      if (machine) {
        const want = machine.st.map((s) => s.state === 'idle' || s.state === 'on');
        const lk = await evaluate(`__film.look(${JSON.stringify(want)})`);
        machine.step(t, lk);
        const tl = machine.st.map((s) => (s.tin === null ? null : { in: s.tin, out: s.tout ?? Infinity }));
        states = tl.map((ev) => opacityAt(ev, t));
      } else states = (timeline ?? []).map((ev) => opacityAt(ev && { in: ev.in, out: ev.out }, t));
      if (!DRY) await evaluate(`__film.draw(${JSON.stringify(states)})`);
    }
    if (!DRY) {
      if (i % 50 === 0 && !OVERRIDE) { const [a, b, c] = await inner(); if (Math.round(a * c) !== W || Math.round(b * c) !== H) throw new Error(`the window changed size: ${a}x${b} at ${c}`); }
      const shot = await send('Page.captureScreenshot', { format: 'jpeg', quality: 92 });
      await feed(Buffer.from(shot.data, 'base64'));
    }
    const done = (i - from) / stepFrames + 1;
    if (done % 50 === 0 || i + stepFrames >= to) {
      const per = (Date.now() - t0) / done, eta = per * ((to - i) / stepFrames) / 1000;
      console.log(`frame ${done}  t=${t.toFixed(1)} s  ${(per / 1000).toFixed(2)} s/frame  eta ${Math.floor(eta / 60)} min ${Math.round(eta % 60)} s`);
    }
  }
  report.clearance = clearLog;
  const bad = clearLog.filter((c) => c.above > 0);
  console.log(`clearance: ${bad.length} of ${clearLog.length} checks with something within 110 m above the camera; least over what is below: ${Math.min(...clearLog.map((c) => c.over)).toFixed(1)} m`);
  if (timeline && !partial) {
    report.labels = route.labels.map((l, i) => ({ name: l.name, ...(timeline[i] ? { in: +timeline[i].in.toFixed(1), out: +timeline[i].out.toFixed(1) } : {}) }));
    const shown = report.labels.filter((r) => r.in !== undefined).sort((a, b) => a.in - b.in);
    console.log(`labels: ${shown.length} of ${route.labels.length} shown`);
    for (const r of shown) console.log(`  label ${r.name}: ${r.in}-${r.out} s`);
    console.log(`  never (frames on screen / room to start / big+near / not hidden): ${report.labels.map((r, i) => [r, i]).filter(([r]) => r.in === undefined).map(([r, i]) => `${r.name} ${['1', '2', '8', '4'].map((b) => FLAGS.filter((f) => f[i] & Number(b)).length).join('/')}`).join('; ')}`);
  }
  if (machine) {
    report.labels = route.labels.map((l, i) => ({ name: l.name, ...(machine.st[i].tin === null ? {} : { in: +machine.st[i].tin.toFixed(2), out: +(machine.st[i].tout ?? ROUTE_SECONDS).toFixed(2) }) }));
    writeFileSync(LABEL_FILE, JSON.stringify({ route: ROUTE_FILE, labels: machine.st.map((s) => (s.tin === null ? null : { in: s.tin, out: s.tout ?? ROUTE_SECONDS })) }, null, 1));
    for (const r of report.labels) console.log(`  label ${r.name}: ${r.in === undefined ? 'never' : `${r.in}-${r.out} s`}`);
  }
  writeFileSync(REPORT, JSON.stringify(report, null, 1));
  ok = true;
} catch (e) {
  console.error(`failed: ${ffError?.message ?? e.stack ?? e}`);
  process.exitCode = 1;
} finally {
  try { await evaluate('__viewer.film.setClock(null)'); } catch { /* the page may be gone */ }
  ws.close();
  if (ff) {
    ff.stdin.end();
    if (!ok && ff.exitCode === null) ff.kill();
    const code = await ffDone;
    if (ok && code !== 0) { console.error(ffError?.message ?? `ffmpeg exited with ${code}`); process.exitCode = 1; }
    else if (ok) console.log(`wrote ${OUTFILE}`);
  }
  if (pageErrors.length) console.log(`page errors (${pageErrors.length}), first: ${pageErrors.slice(0, 3).join(' | ')}`);
}
function startFfmpeg(file) {
  ffDone = new Promise((res) => {
    ff = spawn('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'warning', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', preview ? '23' : '18', '-preset', preview ? 'medium' : 'slow', '-movflags', '+faststart', file], { stdio: ['pipe', 'ignore', 'pipe'] });
    ff.on('error', (e) => { ffError = new Error(`ffmpeg: ${e.message}`); res(-1); });
    ff.on('close', (code) => { if (code) ffError ??= new Error(`ffmpeg exited with ${code}:\n${ffLog.slice(-1500)}`); res(code); });
    ff.stdin.on('error', (e) => { ffError ??= new Error(`ffmpeg's pipe: ${e.message}`); });
    ff.stderr.on('data', (d) => { ffLog += d; });
  });
}
