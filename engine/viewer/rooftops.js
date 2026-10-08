// Rooftop clutter (06c_rooftops.py): what stands on the roofs, invented but plausible, so that roofs seen
// from the air are not flat slabs. What stands where, in which material and colour, is the pipeline's
// (rooftops.json); the shapes and materials here are a library it picks from.
//
// Items arrive per 1 km tile, grouped by roof (see 06c_rooftops.py for the format): stair and lift boxes,
// water tanks, solar water heaters, corrugated sheds, cooling towers, rows of air handlers, skylights, solar
// panel rows, green beds, helipads, window-cleaning cranes, cars on roof car parks, plants. Each is one
// instance of five unit prototypes (box, cylinder, tilted panel on legs, gable, clump of leafy blobs),
// sized, turned and placed per instance; the material code picks what the shader paints on it.
//
// Parapets are not in that data: they are built here from the building tiles' own walls (06_tiles.py), a
// box along the top edge of every wall, so they follow the rendered outline exactly. Their height and
// kind come from the building's facade style and seed (1-1.5 m walls, glass screens on some office
// towers, low or none on steel sheds); none on plant rooms and landmarks, and none where the roof carries
// on into a touching building of about the same height (satellite footprints split some buildings).
//
// Draw calls: one instanced mesh per prototype plus one for the parapets, refilled from the tiles near
// and in view when the camera has moved enough (as trees.js does). Levels of detail by size: small things
// (plants, outdoor units, vents) within SMALL m, tanks and parapets within MID m, stair boxes and the like
// within BIG m, large things (sheds, solar rows, helipads, glass screens) within FAR m; each fades out by
// screen-door dithering over the last fifth of its range. Only items that matter cast shadows (boxes,
// tanks, sheds and panels, parapets; not the plants).
import * as THREE from 'three/webgpu';
import {
  Fn, If, attribute, uniform, varying, vec2, vec3, vec4, float, mix, select, smoothstep, max, min, abs, floor, fract,
  mod, length, normalize, dot, sin, cos, atan, fwidth, hash, screenCoordinate, transformNormalToView, pow, texture, log2,
} from 'three/tsl';

const FAR = 2600, BIG = 1600, MID = 900, SMALL = 420, POTS = 500, STACKS = 1300, SIGNS = 700;
const CONCURRENCY = 4;
const REFILL_MS = 150;

// ---------------------------------------------------------------- prototypes (unit shapes)
// Attributes: position (unit shape, x and z in -0.5..0.5, y in 0..1), normal, offs (metres or a unit
// direction, see each shape), part (which piece of the shape).
function builder() {
  const b = { p: [], n: [], o: [], k: [], i: [] };
  b.vert = (p, n, o = [0, 0, 0], k = 0) => {
    b.p.push(...p); b.n.push(...n); b.o.push(...o); b.k.push(k);
    return b.p.length / 3 - 1;
  };
  // a planar face (3 or 4 corners), wound so its front side faces n
  b.face = (pts, n, k = 0, offs = null) => {
    const [a, c, d] = pts;
    const u = [c[0] - a[0], c[1] - a[1], c[2] - a[2]], v = [d[0] - a[0], d[1] - a[1], d[2] - a[2]];
    const g = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    const flip = g[0] * n[0] + g[1] * n[1] + g[2] * n[2] < 0;
    const ids = pts.map((p, j) => b.vert(p, n, offs ? offs[j] : [0, 0, 0], k));
    const o = flip ? [...ids].reverse() : ids;
    for (let j = 1; j + 1 < o.length; j++) b.i.push(o[0], o[j], o[j + 1]);
  };
  b.geometry = () => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(b.p, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(b.n, 3));
    g.setAttribute('offs', new THREE.Float32BufferAttribute(b.o, 3));
    g.setAttribute('part', new THREE.Float32BufferAttribute(b.k, 1));
    g.setIndex(b.i);
    return g;
  };
  return b;
}

// open box (no bottom): x, z in -0.5..0.5, y 0..1
function openBox(b, x0, x1, z0, z1, k, lid = true, offsFor = null) {
  const P = (x, y, z) => [x, y, z];
  const o = (x, z) => (offsFor ? offsFor(x, z) : [0, 0, 0]);
  if (lid) b.face([P(x0, 1, z0), P(x1, 1, z0), P(x1, 1, z1), P(x0, 1, z1)], [0, 1, 0], k);
  b.face([P(x1, 0, z0), P(x1, 0, z1), P(x1, 1, z1), P(x1, 1, z0)], [1, 0, 0], k, [o(1, -1), o(1, 1), o(1, 1), o(1, -1)]);
  b.face([P(x0, 0, z0), P(x0, 0, z1), P(x0, 1, z1), P(x0, 1, z0)], [-1, 0, 0], k, [o(-1, -1), o(-1, 1), o(-1, 1), o(-1, -1)]);
  b.face([P(x0, 0, z1), P(x1, 0, z1), P(x1, 1, z1), P(x0, 1, z1)], [0, 0, 1], k, [o(-1, 1), o(1, 1), o(1, 1), o(-1, 1)]);
  b.face([P(x0, 0, z0), P(x1, 0, z0), P(x1, 1, z0), P(x0, 1, z0)], [0, 0, -1], k, [o(-1, -1), o(1, -1), o(1, -1), o(-1, -1)]);
}

function boxGeometry() {
  const b = builder();
  openBox(b, -0.5, 0.5, -0.5, 0.5, 0);
  return b.geometry();
}

// cylinder, axis y, radius 0.5, 0..1 (part 0 side, 1 caps) on a stand (part 2, four legs)
function cylinderGeometry(seg = 8) {
  const b = builder();
  const ring = [];
  for (let i = 0; i <= seg; i++) {
    const a = (i / seg) * Math.PI * 2, c = Math.cos(a), s = Math.sin(a);
    ring.push([b.vert([0.5 * c, 0, 0.5 * s], [c, 0, s], [0, 0, 0], 0), b.vert([0.5 * c, 1, 0.5 * s], [c, 0, s], [0, 0, 0], 0)]);
  }
  for (let i = 0; i < seg; i++) {
    const [a0, a1] = ring[i], [b0, b1] = ring[i + 1];
    b.i.push(a0, a1, b1, a0, b1, b0);                   // outward (checked: CCW seen from outside)
  }
  for (const [y, ny] of [[1, 1], [0, -1]]) {
    const pts = [];
    for (let i = 0; i < seg; i++) {
      const a = (i / seg) * Math.PI * 2;
      pts.push([0.5 * Math.cos(a), y, 0.5 * Math.sin(a)]);
    }
    b.face(pts, [0, ny, 0], 1);
  }
  // the stand: four steel legs at the corners (open underneath: the roof shows between them)
  for (const [x, z] of [[-0.38, -0.38], [0.38, -0.38], [-0.38, 0.38], [0.38, 0.38]]) openBox(b, x - 0.04, x + 0.04, z - 0.04, z + 0.04, 2, false);
  return b.geometry();
}

// a cone (the conical roof of a wooden water tank): radius 0.5 at y = 0 to the apex at y = 1, and a base
function coneGeometry(seg = 10) {
  const b = builder();
  const slope = 0.5;                                 // run over rise of the side, for its normals
  for (let i = 0; i < seg; i++) {
    const a0 = (i / seg) * Math.PI * 2, a1 = ((i + 1) / seg) * Math.PI * 2, am = (a0 + a1) / 2;
    const n = (a) => { const l = Math.hypot(1, slope); return [Math.cos(a) / l, slope / l, Math.sin(a) / l]; };
    const v0 = b.vert([0.5 * Math.cos(a0), 0, 0.5 * Math.sin(a0)], n(a0), [0, 0, 0], 0);
    const v1 = b.vert([0.5 * Math.cos(a1), 0, 0.5 * Math.sin(a1)], n(a1), [0, 0, 0], 0);
    const t = b.vert([0, 1, 0], n(am), [0, 0, 0], 0);
    b.i.push(v0, t, v1);
  }
  const pts = [];
  for (let i = 0; i < seg; i++) pts.push([0.5 * Math.cos((i / seg) * Math.PI * 2), 0, 0.5 * Math.sin((i / seg) * Math.PI * 2)]);
  b.face(pts, [0, -1, 0], 1);
  return b.geometry();
}

// a row of chimney pots (Paris's mitrons): POT_SLOTS tapered five-sided pots (part = slot), each with a lid (part
// + 0.5: the flue's dark mouth); the shader spreads the first `param` of them along x and folds the rest away
const POT_SLOTS = 8;
function potsGeometry(seg = 5) {
  const b = builder();
  for (let j = 0; j < POT_SLOTS; j++) {
    const ring = [];
    for (let i = 0; i <= seg; i++) {
      const a = (i / seg) * Math.PI * 2, c = Math.cos(a), s = Math.sin(a);
      ring.push([b.vert([0, 0, 0], [c, 0.12, s], [c, 0, s], j), b.vert([0, 1, 0], [c, 0.12, s], [c, 0, s], j)]);
    }
    for (let i = 0; i < seg; i++) {
      const [a0, a1] = ring[i], [b0, b1] = ring[i + 1];
      b.i.push(a0, a1, b1, a0, b1, b0);
    }
    const lid = [];
    for (let i = 0; i < seg; i++) {
      const a = (i / seg) * Math.PI * 2;
      lid.push(b.vert([0, 1, 0], [0, 1, 0], [Math.cos(a), 0, Math.sin(a)], j + 0.5));
    }
    for (let i = 1; i + 1 < seg; i++) b.i.push(lid[0], lid[i + 1], lid[i]);
  }
  return b.geometry();
}

// tilted panel on legs: a slab (part 0) whose top slopes down towards +z (the front; the shader sets the
// heights from the item's front/back ratio), four legs (part 1, offs = unit direction of the leg's
// thickness), and a tank along the top back edge (part 2, offs = unit circle in y, z)
function panelGeometry(seg = 8) {
  const b = builder();
  const P = (x, y, z) => [x, y, z];
  b.face([P(-0.5, 1, -0.5), P(0.5, 1, -0.5), P(0.5, 1, 0.5), P(-0.5, 1, 0.5)], [0, 1, 0], 0);
  b.face([P(-0.5, 0, -0.5), P(0.5, 0, -0.5), P(0.5, 0, 0.5), P(-0.5, 0, 0.5)], [0, -1, 0], 0);
  b.face([P(0.5, 0, -0.5), P(0.5, 0, 0.5), P(0.5, 1, 0.5), P(0.5, 1, -0.5)], [1, 0, 0], 0);
  b.face([P(-0.5, 0, -0.5), P(-0.5, 0, 0.5), P(-0.5, 1, 0.5), P(-0.5, 1, -0.5)], [-1, 0, 0], 0);
  b.face([P(-0.5, 0, 0.5), P(0.5, 0, 0.5), P(0.5, 1, 0.5), P(-0.5, 1, 0.5)], [0, 0, 1], 0);
  b.face([P(-0.5, 0, -0.5), P(0.5, 0, -0.5), P(0.5, 1, -0.5), P(-0.5, 1, -0.5)], [0, 0, -1], 0);
  for (const lx of [-0.45, 0.45]) {
    for (const lz of [-0.45, 0.45]) {
      // leg: all four corners at the anchor, pushed out by offs (x, z unit) in the shader
      const Q = (y) => [lx, y, lz];
      // the four corners of a face share the anchor and differ only in offs, so wind them explicitly
      const add = (n, c0, c1) => {
        const ids = [b.vert(Q(0), n, c0, 1), b.vert(Q(0), n, c1, 1), b.vert(Q(1), n, c1, 1), b.vert(Q(1), n, c0, 1)];
        // winding: corners c0 -> c1 run counter-clockwise seen from outside when n x (c1 - c0) points up
        const cr = n[2] * (c1[0] - c0[0]) - n[0] * (c1[2] - c0[2]);
        if (cr > 0) b.i.push(ids[0], ids[1], ids[2], ids[0], ids[2], ids[3]);
        else b.i.push(ids[0], ids[2], ids[1], ids[0], ids[3], ids[2]);
      };
      add([1, 0, 0], [1, 0, -1], [1, 0, 1]);
      add([-1, 0, 0], [-1, 0, -1], [-1, 0, 1]);
      add([0, 0, 1], [-1, 0, 1], [1, 0, 1]);
      add([0, 0, -1], [-1, 0, -1], [1, 0, -1]);
    }
  }
  // tank: x from -0.5 to 0.5 at the anchor (x, 1, -0.5); ring in (y, z)
  const rings = [];
  for (let i = 0; i <= seg; i++) {
    const a = (i / seg) * Math.PI * 2, c = Math.cos(a), s = Math.sin(a);
    rings.push([b.vert([-0.5, 1, -0.5], [0, c, s], [0, c, s], 2), b.vert([0.5, 1, -0.5], [0, c, s], [0, c, s], 2)]);
  }
  for (let i = 0; i < seg; i++) {
    const [a0, a1] = rings[i], [b0, b1] = rings[i + 1];
    // CCW from outside: the ring runs from +y towards +z, around +x
    b.i.push(a0, b1, a1, a0, b0, b1);
  }
  for (const sx of [-0.5, 0.5]) {
    const ids = [];
    for (let i = 0; i < seg; i++) {
      const a = (i / seg) * Math.PI * 2;
      ids.push(b.vert([sx, 1, -0.5], [Math.sign(sx), 0, 0], [0, Math.cos(a), Math.sin(a)], 2));
    }
    for (let j = 1; j + 1 < seg; j++) {
      if (sx > 0) b.i.push(ids[0], ids[j], ids[j + 1]);
      else b.i.push(ids[0], ids[j + 1], ids[j]);
    }
  }
  return b.geometry();
}

// gable roof: ridge along x at the top, eaves at z = +-0.5
function gableGeometry() {
  const b = builder();
  const n = Math.hypot(0.5, 1);
  b.face([[-0.5, 0, 0.5], [0.5, 0, 0.5], [0.5, 1, 0], [-0.5, 1, 0]], [0, 1 / n, 0.5 / n], 0);
  b.face([[-0.5, 0, -0.5], [0.5, 0, -0.5], [0.5, 1, 0], [-0.5, 1, 0]], [0, 1 / n, -0.5 / n], 0);
  b.face([[0.5, 0, 0.5], [0.5, 0, -0.5], [0.5, 1, 0]], [1, 0, 0], 0);
  b.face([[-0.5, 0, 0.5], [-0.5, 0, -0.5], [-0.5, 1, 0]], [-1, 0, 0], 0);
  return b.geometry();
}

// three leafy blobs in a row: icosahedra (offs = unit sphere position) at x = -0.5, 0, 0.5 (part = index)
function blobGeometry() {
  const t = (1 + Math.sqrt(5)) / 2;
  const V = [[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
    [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]].map((v) => { const l = Math.hypot(...v); return v.map((c) => c / l); });
  const F = [[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6],
    [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]];
  const b = builder();
  [-0.5, 0, 0.5].forEach((x, j) => {
    const base = b.p.length / 3;
    for (const v of V) b.vert([x, 0, 0], v, v, j);
    for (const f of F) b.i.push(base + f[0], base + f[1], base + f[2]);
  });
  return b.geometry();
}

// ---------------------------------------------------------------- shading helpers
const f01 = (c) => select(c, float(1), float(0));
const num = (x) => (typeof x === 'number' ? float(x) : x);
// 1 on lines of half-width w (metres) every `period` metres of t; fades to its mean once finer than a pixel
function lines(t, period, w, fw) {
  const p = num(period), hw = num(w);
  const d = abs(fract(t.div(p).add(0.5)).sub(0.5)).mul(p);
  const aa = max(fw, 1e-4);
  const v = float(1).sub(smoothstep(hw.sub(aa), hw.add(aa), d));
  return mix(v, min(hw.mul(2).div(p), 1), smoothstep(p.mul(0.2), p.mul(0.5), fw));
}
// 1 where lo < x < hi, anti-aliased
const inside = (x, lo, hi, fw) => {
  const aa = max(fw, 1e-4);
  return smoothstep(num(lo).sub(aa), num(lo).add(aa), x).mul(float(1).sub(smoothstep(num(hi).sub(aa), num(hi).add(aa), x)));
};
// 1 inside a disc of radius r
const disc = (x, z, r, fw) => { const aa = max(fw, 1e-4); return float(1).sub(smoothstep(num(r).sub(aa), num(r).add(aa), length(vec2(x, z)))); };
const h2 = (a, b) => hash(a.mul(12.9898).add(b.mul(78.233)));
function vnoise(x, z) {
  const ix = floor(x), iz = floor(z), fx = fract(x), fz = fract(z);
  const ux = fx.mul(fx).mul(fx.mul(-2).add(3)), uz = fz.mul(fz).mul(fz.mul(-2).add(3));
  return mix(mix(h2(ix, iz), h2(ix.add(1), iz), ux), mix(h2(ix, iz.add(1)), h2(ix.add(1), iz.add(1)), ux), uz);
}
const unpack = (packed) => {                       // 24-bit sRGB -> linear
  const p = packed.add(0.5);
  const r = floor(p.div(65536)), g = floor(p.div(256)).sub(r.mul(256)), b = floor(p).sub(floor(p.div(256)).mul(256));
  return pow(vec3(r, g, b).div(255), vec3(2.2));
};

// ---------------------------------------------------------------- materials
const U = { camPos: uniform(new THREE.Vector3()) };
const ra = attribute('ra', 'vec4');               // x, y, z (scene, bottom centre), yaw (radians)
const rb = attribute('rb', 'vec4');               // size x, y, z (m), material + 32 x param
const rc = attribute('rc', 'vec2');               // packed sRGB colour, fade-out distance
const P0 = attribute('position', 'vec3'), N0 = attribute('normal', 'vec3');
const OF = attribute('offs', 'vec3'), PART = attribute('part', 'float');
const dither = fract(float(52.9829189).mul(fract(dot(screenCoordinate.xy, vec2(0.06711056, 0.00583715)))));

// look (city.json rooftopLook, opt-in; Paris): potsFar, the chimney pots' colour (linear) seen from beyond their own
// range: there the stacks carry a band of that colour on top, as tall as a row of pots, so the warm speckle of the
// pot rows along the party walls stays in views from a kilometre and more; stacks, the stacks' range (m)
function rooftopMaterial(proto, M, look = {}) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.85, metalness: 0 });
  const size = rb.xyz, code = rb.w.add(0.5);
  const matId = floor(mod(code, 32)), param = floor(code.div(32));
  const cy = cos(ra.w), sy = sin(ra.w);
  const turn = (v) => vec3(v.x.mul(cy).add(v.z.mul(sy)), v.y, v.x.mul(sy).negate().add(v.z.mul(cy)));
  const seed = hash(ra.x.mul(0.731).add(ra.z.mul(1.379)).add(0.5));
  let L, NL;
  if (proto === 'cylinder') {
    const stand = floor(param.div(2)).mul(0.05), lying = mod(param, 2);
    const body = f01(PART.lessThan(1.5));
    const hb = size.y.sub(stand);
    const up = vec3(P0.x.mul(size.x), stand.add(P0.y.mul(hb)), P0.z.mul(size.z));
    const side = vec3(P0.y.sub(0.5).mul(size.x), stand.add(P0.x.add(0.5).mul(hb)), P0.z.negate().mul(size.z));
    const standP = vec3(P0.x.mul(size.x), P0.y.mul(stand), P0.z.mul(size.z));
    L = mix(standP, mix(up, side, lying), body);
    const nUp = N0, nSide = vec3(N0.y, N0.x, N0.z.negate());
    NL = normalize(mix(nUp, nSide, lying.mul(body)).div(vec3(size.x, mix(size.y, size.x, lying.mul(body)), size.z).max(0.05)));
  } else if (proto === 'panel') {
    const f = mod(param, 128).div(127), tank = f01(param.greaterThan(127.5));
    const T = select(matId.equal(M.corrugated), float(0.05), float(0.07));
    const hs = (z) => size.y.mul(f.add(float(1).sub(f).mul(float(0.5).sub(z))));
    const legW = select(matId.equal(M.corrugated), float(0.05), select(matId.equal(M.pv), float(0.0), float(0.025)));
    const slab = vec3(P0.x.mul(size.x), hs(P0.z).sub(T.mul(float(1).sub(P0.y))), P0.z.mul(size.z));
    const leg = vec3(P0.x.mul(size.x).add(OF.x.mul(legW)), P0.y.mul(hs(P0.z).sub(T)), P0.z.mul(size.z).add(OF.z.mul(legW)));
    const R = float(0.24).mul(tank);
    const tankP = vec3(P0.x.mul(size.x).mul(tank), hs(float(-0.5)).add(R.mul(0.6)).add(OF.y.mul(R)),
      size.z.mul(-0.5).add(R).add(OF.z.mul(R)));
    const isSlab = f01(PART.lessThan(0.5)), isLeg = f01(PART.greaterThan(0.5).and(PART.lessThan(1.5)));
    L = mix(mix(tankP, leg, isLeg), slab, isSlab);
    const nTop = normalize(vec3(0, 1, float(1).sub(f).mul(size.y).div(size.z)));
    const nSlab = select(N0.y.greaterThan(0.5), nTop, select(N0.y.lessThan(-0.5), nTop.negate(), N0));
    NL = mix(N0, nSlab, isSlab);
  } else if (proto === 'pots') {
    // pot j of n (param) at its slot along x, a little taller or shorter than its neighbours; slots past n fold away
    const j = floor(PART), n = max(param, 1);
    const on = f01(j.lessThan(n));
    const hj = hash(seed.add(j.mul(0.371)));
    const cx = j.add(0.5).div(n).sub(0.5).mul(size.x);
    const r = size.z.mul(0.5).mul(float(1).sub(P0.y.mul(0.2))).mul(hj.mul(0.25).add(0.85));
    L = vec3(cx.add(OF.x.mul(r)), P0.y.mul(size.y).mul(hj.mul(0.45).add(0.75)), OF.z.mul(r)).mul(on);
    NL = N0;
  } else if (proto === 'blob') {
    const k = hash(seed.add(PART.mul(0.37))).mul(0.4).add(0.8);
    L = vec3(P0.x.mul(size.x.sub(size.z)).add(OF.x.mul(size.z).mul(0.5).mul(k)),
      size.y.mul(0.5).add(OF.y.mul(size.y).mul(0.5).mul(k)), OF.z.mul(size.z).mul(0.5).mul(k));
    NL = N0;
  } else {
    L = P0.mul(size);
    NL = normalize(N0.div(size.max(0.01)));
  }
  // (look.potsFar: a stack's pot band, 0.6 m, grows in as its pots fade out)
  const potBand = look.potsFar && proto === 'box' && M.chimney !== undefined
    ? smoothstep(POTS * 0.8, POTS, length(ra.xyz.sub(U.camPos))).mul(f01(matId.equal(M.chimney))) : null;
  if (potBand) L = L.add(vec3(0, P0.y.mul(potBand).mul(0.6), 0));
  m.positionNode = turn(L).add(ra.xyz);
  const vNW = varying(turn(NL));
  m.normalNode = transformNormalToView(normalize(vNW));
  const vL = varying(L), vN = varying(NL), vPart = varying(PART), vSize = varying(size);
  const vMat = varying(matId), vParam = varying(param), vCol = varying(unpack(rc.x)), vSeed = varying(seed);
  const vFade = varying(smoothstep(rc.y.mul(0.8), rc.y, length(ra.xyz.sub(U.camPos))));
  const vPotBand = potBand ? varying(potBand) : null;
  m.maskNode = vFade.lessThan(dither);

  const shaded = Fn(() => {
    // ---- colour and roughness, per material (one branch runs per instance). Derivatives are taken here,
    // before the branches: WGSL allows them only in uniform control flow
    const fwL = fwidth(vL).toVar();
    const top = vN.y.greaterThan(0.6).toVar();
    const onX = abs(vN.x).greaterThan(abs(vN.z)).toVar();
    const u = select(onX, vL.z, vL.x).toVar();         // along a side face
    const fwU = select(onX, fwL.z, fwL.x).toVar(), fwY = fwL.y.toVar();
    const fwH = max(fwL.x, fwL.z).toVar();
    const S = vSize, C = vCol, sd = vSeed;
    const X = vL.x, Y = vL.y, Z = vL.z;
    const col = vec3(0.5).toVar(), rough = float(0.85).toVar();
    const noise = vnoise(positionWorldish(vL, sd).x, positionWorldish(vL, sd).y).toVar();
    const is = (name) => (M[name] === undefined ? float(0).greaterThan(1) : vMat.equal(M[name]));
    const roofGrey = (k) => vec3(0.3, 0.295, 0.285).mul(k);

    if (M.parapet !== undefined) {
      If(is('parapet'), () => {
        // outer face (-z) continues the facade, the inner face is plain render with grime at its foot;
        // the top is a coping, lighter
        const inner = vN.z.greaterThan(0.5);
        const foot = smoothstep(0, 0.35, Y);
        const panel = lines(X, 3, 0.02, fwH).mul(0.08);
        col.assign(select(top, C.mul(1.08).add(0.025), select(inner, C.mul(mix(0.55, 0.86, foot)), C.mul(0.97)))
          .mul(float(1).sub(panel)).mul(noise.mul(0.1).add(0.95)));
        rough.assign(0.9);
      });
    }
    if (M.screen !== undefined) {
      If(is('screen'), () => {
        // glass screen: dark tinted glass between aluminium mullions, a metal cap
        const mull = max(lines(X, 1.5, 0.04, fwH), smoothstep(S.y.sub(0.25), S.y.sub(0.2), Y));
        col.assign(select(top, vec3(0.45, 0.46, 0.47), mix(C.mul(0.32), vec3(0.4, 0.41, 0.42), mull)));
        rough.assign(select(top, float(0.5), mix(0.12, 0.5, mull)));
      });
    }
    if (M.concrete !== undefined) {
      If(is('concrete').or(is('stair')), () => {
        const stain = smoothstep(0.35, 0.9, noise).mul(0.12);
        // stair and lift boxes: a door (steel, painted or timber) on the front and a small window
        const door = f01(is('stair')).mul(f01(vN.z.greaterThan(0.5))).mul(inside(X, sd.sub(0.5).mul(S.x.sub(1.4)).sub(0.5),
          sd.sub(0.5).mul(S.x.sub(1.4)).add(0.5), fwU)).mul(inside(Y, 0.02, 2.05, fwY));
        const win = f01(is('stair')).mul(f01(onX)).mul(inside(Z, -0.35, 0.35, fwU)).mul(inside(Y, S.y.sub(1.1), S.y.sub(0.5), fwY));
        const doorCol = select(sd.greaterThan(0.6), vec3(0.08, 0.09, 0.1), select(sd.greaterThan(0.3), vec3(0.24, 0.12, 0.07), vec3(0.12, 0.25, 0.3)));
        // plant enclosures (param 1): a band of louvres round the walls
        const louvre = f01(vParam.greaterThan(0.5)).mul(inside(Y, 0.6, S.y.sub(0.4), fwY))
          .mul(lines(Y, 0.1, 0.03, fwY).mul(0.5).add(0.25));
        const walls = C.mul(float(0.97).sub(stain)).mul(mix(float(0.8), float(1), smoothstep(0, 0.5, Y)))
          .mul(float(1).sub(louvre));
        // the lid: roof concrete, darker towards its edges where rain runs off
        const rim = max(abs(X).div(S.x), abs(Z).div(S.z)).mul(2);
        const topC = roofGrey(float(1.05).sub(stain)).mul(float(1).sub(smoothstep(0.8, 1.0, rim).mul(0.2)));
        col.assign(select(top, topC, mix(mix(walls, doorCol, door), vec3(0.07, 0.08, 0.09), win)));
        rough.assign(0.9);
      });
    }
    if (M.hvac !== undefined) {
      If(is('hvac').or(is('cooling')), () => {
        // rows of units side by side (param = how many): joints between them, fan grilles on top,
        // louvres on the sides; cooling towers have one big fan per cell over a dark deck
        const n = max(vParam, 1), w = S.x.div(n);
        const ux = fract(X.add(S.x.mul(0.5)).div(w)).sub(0.5).mul(w);
        const joint = lines(X.add(S.x.mul(0.5)), w, 0.04, fwH);
        const cool = is('cooling');
        const r = min(w, S.z).mul(select(cool, float(0.42), float(0.3)));
        const fan = disc(ux, Z, r, fwH);
        const rim = fan.sub(disc(ux, Z, r.sub(0.12), fwH)).max(0);
        const blades = f01(fract(atan(Z, ux).mul(6 / (2 * Math.PI))).lessThan(0.5)).mul(0.08);
        const topU = select(cool, vec3(0.1, 0.105, 0.11), C.mul(0.92));
        const topC = mix(mix(topU, vec3(0.05, 0.05, 0.055).add(blades), fan), vec3(0.32, 0.33, 0.34), rim);
        const louvre = lines(Y, select(cool, float(0.14), float(0.07)), select(cool, float(0.04), float(0.018)), fwY)
          .mul(inside(Y, 0.15, S.y.sub(0.2), fwY));
        const sideC = C.mul(float(1).sub(louvre.mul(0.45))).mul(mix(0.85, 1.0, smoothstep(0, 0.4, Y)));
        col.assign(select(top, topC, sideC).mul(float(1).sub(joint.mul(0.5))));
        rough.assign(0.6);
      });
    }
    if (M.paneltank !== undefined) {
      If(is('paneltank'), () => {
        // sectional tank: 1 m panels with bolted flanges
        const g = max(lines(u.add(S.x.mul(0.5)), 1, 0.035, select(top, fwH, fwU)),
          select(top, lines(Z.add(S.z.mul(0.5)), 1, 0.035, fwH), lines(Y, 1, 0.035, fwY)));
        const dome = select(top, float(0), float(0));
        col.assign(C.mul(float(1).sub(g.mul(0.35)).add(dome)).mul(select(top, float(0.95), float(1))));
        rough.assign(0.55);
      });
    }
    if (M.steel !== undefined) {
      If(is('steel'), () => { col.assign(C.mul(select(top, float(1.05), float(0.92)))); rough.assign(0.55); });
    }
    if (M.skylight !== undefined) {
      If(is('skylight'), () => {
        // glass with mullions every 1.2 m; strips (param 1) are ribbed translucent sheets
        const strip = vParam.greaterThan(0.5);
        const glassFace = select(proto === 'gable' ? float(1).greaterThan(0) : top, float(1), float(0));
        const mull = max(lines(X, 1.2, 0.04, fwH), lines(Z, select(strip, float(0.25), float(1.2)), select(strip, float(0.03), float(0.04)), fwH));
        const glass = mix(vec3(0.16, 0.2, 0.23), vec3(0.4, 0.42, 0.43), mull);
        const poly = vec3(0.62, 0.65, 0.64).mul(float(1).sub(mull.mul(0.2)));
        col.assign(mix(vec3(0.34, 0.35, 0.36), select(strip, poly, glass), glassFace));
        rough.assign(mix(0.5, select(strip, float(0.35), float(0.06)), glassFace));
      });
    }
    if (M.green !== undefined) {
      If(is('green'), () => {
        const rim = float(1).sub(inside(X, S.x.mul(-0.5).add(0.25), S.x.mul(0.5).sub(0.25), fwH)
          .mul(inside(Z, S.z.mul(-0.5).add(0.25), S.z.mul(0.5).sub(0.25), fwH)));
        const tuft = vnoise(X.mul(1.3).add(sd.mul(50)), Z.mul(1.3)).mul(0.6).add(noise.mul(0.4));
        const plant = C.mul(tuft.mul(0.7).add(0.6));
        col.assign(select(top, mix(plant, vec3(0.42, 0.41, 0.39), rim), vec3(0.4, 0.39, 0.37)));
        rough.assign(0.95);
      });
    }
    if (M.helipad !== undefined) {
      If(is('helipad'), () => {
        // helipad: an edge line, a touchdown circle and an H, white (some yellow circles)
        const D = S.x, r = length(vec2(X, Z));
        const edge = float(1).sub(inside(X, D.mul(-0.5).add(0.5), D.mul(0.5).sub(0.5), fwH).mul(inside(Z, D.mul(-0.5).add(0.5), D.mul(0.5).sub(0.5), fwH)))
          .mul(inside(X, D.mul(-0.5).add(0.2), D.mul(0.5).sub(0.2), fwH)).mul(inside(Z, D.mul(-0.5).add(0.2), D.mul(0.5).sub(0.2), fwH));
        const ring = inside(r, D.mul(0.3), D.mul(0.3).add(0.4), fwH);
        const hw = D.mul(0.11), hh = D.mul(0.15), st = D.mul(0.035);
        const H = max(inside(Z, hh.negate(), hh, fwH).mul(max(inside(X, hw.negate(), hw.negate().add(st), fwH), inside(X, hw.sub(st), hw, fwH))),
          inside(X, hw.negate(), hw, fwH).mul(inside(Z, st.mul(-0.5), st.mul(0.5), fwH)));
        const white = vec3(0.78, 0.78, 0.76), yellow = vec3(0.75, 0.6, 0.12);
        const topC = mix(mix(C, select(sd.greaterThan(0.5), yellow, white), ring), white, max(edge, H));
        col.assign(select(top, topC, C.mul(0.6)));
        rough.assign(0.8);
      });
    }
    if (M.parking !== undefined) {
      If(is('parking'), () => {
        // bays 2.5 m wide in pairs of 5 m rows with a 6 m aisle between pairs (as 06c_rooftops.py lays out the cars)
        const zz = S.z.mul(0.5).sub(Z), period = mod(zz, 16);
        const bays = inside(period, 0, 10, fwH);
        const sep = lines(X.add(S.x.mul(0.5)).sub(1), 2.5, 0.06, fwH).mul(bays);
        const mid = lines(period, 16, 0.06, fwH).max(lines(period.sub(5), 16, 0.06, fwH));
        col.assign(select(top, mix(C.mul(noise.mul(0.2).add(0.9)), vec3(0.7, 0.7, 0.68), max(sep, mid.mul(bays))), vec3(0.35, 0.35, 0.34)));
        rough.assign(0.9);
      });
    }
    if (M.car !== undefined) {
      If(is('car'), () => {
        // cars: glass roof band on top (windscreen, roof, rear window), dark windows and wheels on the sides
        const l = X.div(S.x);
        const glassTop = max(inside(l, 0.08, 0.26, fwH.div(S.x)), inside(l, -0.33, -0.2, fwH.div(S.x)))
          .mul(inside(Z, S.z.mul(-0.42), S.z.mul(0.42), fwH));
        const roofTop = inside(l, -0.2, 0.08, fwH.div(S.x));
        const glass = vec3(0.03, 0.035, 0.04);
        const sideWin = inside(Y, S.y.mul(0.58), S.y.mul(0.9), fwY).mul(inside(l, -0.3, 0.25, fwH.div(S.x)));
        const wheel = inside(Y, 0, S.y.mul(0.35), fwY).mul(max(inside(l, 0.22, 0.38, fwH.div(S.x)), inside(l, -0.38, -0.22, fwH.div(S.x))));
        const topC = mix(C.mul(select(roofTop.greaterThan(0.5), float(0.95), float(1.05))), glass, glassTop);
        col.assign(select(top, topC, mix(mix(C, glass, sideWin), vec3(0.02), wheel)));
        rough.assign(mix(0.3, 0.1, glassTop));
      });
    }
    if (M.stainless !== undefined) {
      If(is('stainless').or(is('plastic')).or(is('turbine')).or(is('cooling')), () => {
        const stand = vPart.greaterThan(1.5);
        const lying = mod(vParam, 2).greaterThan(0.5);
        const cap = vPart.greaterThan(0.5).and(stand.not());
        // side coordinates: height along the axis and angle around it
        const ax = select(lying, X.add(S.x.mul(0.5)), Y);
        const ang = select(lying, atan(Z, Y.sub(S.y.sub(S.z.mul(0.5)))), atan(Z, X));
        const rad = select(lying, S.z, S.x).mul(0.5);
        const fwAx = select(lying, fwL.x, fwY);
        const around = ang.mul(rad);                      // metres around
        const steel = is('stainless');
        const weld = lines(ax.sub(select(lying, float(0), floor(vParam.div(2)).mul(0.05))), select(lying, S.x.div(3), S.y.div(3)), 0.02, fwAx);
        const ribs = lines(ax, 0.28, 0.05, fwAx);
        const fins = lines(around, 0.12, 0.035, fwH);
        const coolLouvre = lines(ax, 0.14, 0.04, fwAx);
        const sideC = select(steel, C.mul(float(1).sub(weld.mul(0.35))).mul(vnoise(around.mul(3), sd.mul(9)).mul(0.1).add(0.95)),
          select(is('plastic'), C.mul(float(1).sub(ribs.mul(0.18))),
            select(is('turbine'), C.mul(float(1).sub(fins.mul(0.45))), C.mul(float(1).sub(coolLouvre.mul(0.4))))));
        // caps: a lid on tanks, a dome of vanes on ventilators, a fan in a dark deck on cooling towers
        const cr = length(vec2(X, Z));
        const lid = disc(X, Z, 0.22, fwH);
        const fan = disc(X, Z, S.x.mul(0.42), fwH);
        const capC = select(is('cooling'), mix(vec3(0.12, 0.125, 0.13), vec3(0.05, 0.05, 0.055), fan),
          select(is('turbine'), C.mul(float(1).sub(lines(atan(Z, X).mul(cr), 0.1, 0.03, fwH).mul(0.4))),
            C.mul(float(1.04).sub(lid.mul(0.12)))));
        col.assign(select(stand, vec3(0.09, 0.095, 0.1), select(cap.and(lying.not()), capC, sideC)));
        rough.assign(select(stand, float(0.6), select(steel.or(is('turbine')), float(0.3), float(0.5))));
      });
    }
    if (M.wood !== undefined) {
      If(is('wood'), () => {
        // New York's wooden water tanks: cedar staves (vertical), steel hoops, weathered grey-brown; the stand
        // of dark steel under them
        const stand = vPart.greaterThan(1.5);
        const around = atan(Z, X).mul(length(vec2(X, Z)));
        const staves = lines(around, 0.15, 0.025, fwH);
        const hoops = lines(Y, 0.5, 0.05, fwY).mul(select(top, float(0), float(1)));
        const weather = vnoise(around.mul(1.3), Y.mul(0.6).add(sd.mul(7))).mul(0.3).add(0.82);
        col.assign(select(stand, vec3(0.05, 0.05, 0.055),
          C.mul(weather).mul(float(1).sub(staves.mul(0.22))).mul(float(1).sub(hoops.mul(0.55)))));
        rough.assign(select(stand, float(0.6), float(0.92)));
      });
    }
    if (M.tubes !== undefined) {
      If(is('tubes').or(is('pv')).or(is('corrugated')), () => {
        const slab = vPart.lessThan(0.5), tank = vPart.greaterThan(1.5);
        const topS = slab.and(vN.y.greaterThan(0.3));
        // solar water heaters: evacuated tubes down the slope over a white reflector, one unit per ~2 m
        const n = max(floor(S.x.div(2).add(0.5)), 1), w = S.x.div(n);
        const xu = X.add(S.x.mul(0.5));
        const gap = lines(xu, w, 0.05, fwH);
        const tube = lines(X, 0.075, 0.026, fwH);
        const glint = lines(X.add(0.008), 0.075, 0.006, fwH);
        const tubesC = mix(mix(vec3(0.55, 0.56, 0.56), vec3(0.018, 0.022, 0.032), tube), vec3(0.3, 0.32, 0.35), glint.mul(tube));
        const frame = float(1).sub(inside(Z, S.z.mul(-0.5).add(0.06), S.z.mul(0.5).sub(0.06), fwH));
        const heater = mix(tubesC, vec3(0.5, 0.51, 0.52), max(gap, frame));
        // solar panels: cells in 1 x 1.7 m modules with silver frames
        const mod1 = max(lines(X, 1.0, 0.018, fwH), lines(Z.add(S.z.mul(0.5)), 1.05, 0.018, fwH));
        const cells = max(lines(X, 0.166, 0.006, fwH), lines(Z, 0.166, 0.006, fwH));
        const pv = mix(C.mul(float(1).sub(cells.mul(0.25))).mul(vnoise(X.mul(0.5), Z.add(sd.mul(40)).mul(0.5)).mul(0.12).add(0.94)),
          vec3(0.42, 0.43, 0.45), mod1);
        // corrugated steel: ribs down the slope, rust and dirt in patches
        const rib = lines(X, 0.2, 0.05, fwH);
        const dirt = smoothstep(0.7, 0.98, noise).mul(0.12);
        const sheet = mix(C.mul(float(1).sub(rib.mul(0.22))), vec3(0.3, 0.2, 0.14), dirt);
        const topC = select(is('tubes'), heater, select(is('pv'), pv, sheet));
        const under = select(is('corrugated'), C.mul(0.45), vec3(0.3, 0.31, 0.32));
        col.assign(select(tank, vec3(0.62, 0.63, 0.63), select(topS, topC, select(slab, under, vec3(0.2, 0.21, 0.22)))));
        rough.assign(select(topS, select(is('tubes'), float(0.25), select(is('pv'), float(0.22), float(0.5))), float(0.5)));
      });
    }
    if (M.tile !== undefined) {
      If(is('tile'), () => {
        // tiled hat: courses down the slope, joints staggered, a ridge; plastered gable ends
        const slope = abs(vN.x).lessThan(0.5);
        const course = lines(abs(Z), 0.22, 0.03, fwH);
        const joint = lines(X.add(select(mod(floor(abs(Z).div(0.22)), 2).greaterThan(0.5), float(0.12), float(0))), 0.24, 0.02, fwH);
        const ridge = smoothstep(S.y.sub(0.15), S.y.sub(0.1), Y);
        const tileC = C.mul(float(1).sub(course.mul(0.35)).sub(joint.mul(0.15))).mul(noise.mul(0.15).add(0.92));
        col.assign(select(slope, mix(tileC, C.mul(0.7), ridge), vec3(0.62, 0.6, 0.56)));
        rough.assign(0.7);
      });
    }
    if (M.chimney !== undefined) {
      If(is('chimney'), () => {
        // chimney stack: render (or brick courses on the reddish ones), a projecting band and coping at the top,
        // soot streaks running down from it; the top dark with the flues' openings under the pots
        const brick = f01(C.x.greaterThan(C.z.mul(1.3)));
        const courses = lines(Y, 0.075, 0.008, fwY).mul(brick).mul(0.25);
        const soot = smoothstep(S.y.sub(1.4), S.y, Y).mul(vnoise(u.mul(3).add(sd.mul(17)), Y.mul(0.8)).mul(0.35).add(0.1));
        const band = inside(Y, S.y.sub(0.32), S.y.sub(0.2), fwY).mul(0.12);
        const side = C.mul(float(1).sub(courses).sub(soot)).mul(noise.mul(0.12).add(0.94)).add(band.mul(0.08));
        if (potBand) {
          // beyond the pots' range: the band above the stack's own top in the pots' colour, its top their dark mouths
          const potC = vec3(...look.potsFar).mul(hash(sd.mul(41.3)).mul(0.3).add(0.85));
          const inBand = Y.greaterThan(S.y.add(0.01));
          col.assign(select(top, select(vPotBand.greaterThan(0.01), mix(C.mul(0.42), potC.mul(0.55), vPotBand), C.mul(0.42)),
            select(inBand, potC, side)));
        } else col.assign(select(top, C.mul(0.42), side));
        rough.assign(0.92);
      });
    }
    if (M.pot !== undefined) {
      If(is('pot'), () => {
        // terracotta pots, blackened at the mouth; some are grey zinc cowls; the lid is the flue's dark mouth
        const j = floor(vPart);
        const hj = hash(sd.add(j.mul(0.771)));
        const lid = fract(vPart).greaterThan(0.25);
        const clay = C.mul(hj.mul(0.3).add(0.8)).mul(mix(float(1), float(0.55), smoothstep(S.y.mul(0.5), S.y, Y)));
        const zincC = vec3(0.34, 0.36, 0.37).mul(hj.mul(0.3).add(0.8));
        col.assign(select(lid, vec3(0.03, 0.028, 0.026), select(hj.greaterThan(0.84), zincC, clay)));
        rough.assign(select(hj.greaterThan(0.84), float(0.45), float(0.8)));
      });
    }
    if (M.velux !== undefined) {
      If(is('velux').or(is('zinc')), () => {
        // Velux: dark glass in a zinc-grey frame; zinc (hatches, upstands): standing seams on top
        const frame = float(1).sub(inside(X, S.x.mul(-0.5).add(0.07), S.x.mul(0.5).sub(0.07), fwH)
          .mul(inside(Z, S.z.mul(-0.5).add(0.07), S.z.mul(0.5).sub(0.07), fwH)));
        const zincC = vec3(0.3, 0.32, 0.335).mul(noise.mul(0.1).add(0.95));
        const glass = mix(C, vec3(0.3, 0.33, 0.36), smoothstep(0.55, 0.95, noise).mul(0.3));
        const seams = lines(X, 0.5, 0.02, fwH).mul(0.25);
        const zincTop = C.mul(float(1).sub(seams)).mul(noise.mul(0.12).add(0.94));
        col.assign(select(is('velux'), select(top, mix(glass, zincC, frame), zincC), select(top, zincTop, C.mul(0.9))));
        rough.assign(select(is('velux').and(top).and(frame.lessThan(0.5)), float(0.08), float(0.5)));
      });
    }
    if (M.foliage !== undefined) {
      If(is('foliage'), () => {
        const leaf = vnoise(X.mul(4).add(sd.mul(30)), Y.mul(4).add(Z.mul(3))).mul(0.5).add(noise.mul(0.3));
        col.assign(C.mul(leaf.mul(0.7).add(0.55)).mul(mix(0.55, 1.0, smoothstep(0, S.y.mul(0.6), Y))));
        rough.assign(0.95);
      });
    }
    return vec4(col, rough);
  })();
  m.colorNode = shaded.xyz;
  m.roughnessNode = shaded.w;
  return m;
}
// ---------------------------------------------------------------- street signs (Hong Kong's light boxes)
// A board standing out from the wall at right angles (06c_rooftops, preset hk-hongkong: x out from the wall, y up, z
// along it): its two faces (+-z, read along the street) in the board's colour inside a pale rim, with a column of glyphs
// down an upright board or a row along a wide one in a contrasting ink (light on dark boards, red or black on light
// ones), each glyph a block with strokes cut out of it by its hash, averaged out once a glyph is under a few pixels; the
// edges dark steel. After dark (night.withLights) the faces glow: the board's colour and its brighter glyphs (neon and
// light boxes), two in three boards lit, the rest dim.
// (rooftopLook.signGlyphs "atlas", Hong Kong M8 fix round 1, opt-in) real Chinese characters for the boards: the common
// characters of Hong Kong's shop signs drawn once on a canvas (16 x 16 cells of 64 px, white on clear, in the system's
// CJK sans: Noto Sans CJK TC, PingFang TC, Microsoft JhengHei), each glyph cell of a board one of them by its hash; the
// stroke grids of "cjk" read as Korean Hangul (Known issue 82)
const SIGN_CHARS = '藥房酒家茶餐廳金行珠寶找換地產眼鏡時裝鞋按摩麻雀當押大小食飯店粥麵燒臘海鮮樓冰室牛雜銀電器中西醫診所牙科補習社旅館賓髮型美容新華興隆昌記號公司有限堂參茸味錶數碼手機通訊夜總會卡拉鴻福利祥發財源豐泰盛和記興記粉麵火鍋點心燉品糖水士多涼茶舖百貨文具玩具影印快餐腸粉魚蛋雞煲仔菜館潮州上海四川台灣日本韓國越南泰式按揭財務洗衣乾洗冷氣五金水喉油漆傢俬床褥窗簾燈飾電腦維修專門港九龍旺角深水埗灣仔銅鑼尖沙咀天后北角筲箕';
let signAtlas = null;
function signGlyphAtlas() {
  if (signAtlas) return signAtlas;
  const n = 16, px = 64, cv = document.createElement('canvas');
  cv.width = cv.height = n * px;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.font = `bold ${px * 0.84}px "Noto Sans CJK TC", "PingFang TC", "Microsoft JhengHei", "Noto Sans CJK SC", sans-serif`;
  const chars = [...SIGN_CHARS];
  for (let i = 0; i < n * n; i++) ctx.fillText(chars[i % chars.length], (i % n + 0.5) * px, (Math.floor(i / n) + 0.53) * px);
  signAtlas = new THREE.CanvasTexture(cv);
  signAtlas.flipY = false;
  signAtlas.generateMipmaps = true;
  signAtlas.minFilter = THREE.LinearMipmapLinearFilter;
  signAtlas.colorSpace = THREE.NoColorSpace;
  return signAtlas;
}
function signMaterial(night, look = {}) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.5, metalness: 0 });
  const size = rb.xyz;
  const cy = cos(ra.w), sy = sin(ra.w);
  const turn = (v) => vec3(v.x.mul(cy).add(v.z.mul(sy)), v.y, v.x.mul(sy).negate().add(v.z.mul(cy)));
  const L = P0.mul(size);
  m.positionNode = turn(L).add(ra.xyz);
  const vNW = varying(turn(normalize(N0.div(size.max(0.01)))));
  m.normalNode = transformNormalToView(normalize(vNW));
  const vL = varying(L), vN = varying(N0), vSize = varying(size), vCol = varying(unpack(rc.x));
  const vSeed = varying(hash(ra.x.mul(0.731).add(ra.z.mul(1.379)).add(ra.y.mul(0.917)).add(0.5)));
  const vFade = varying(smoothstep(rc.y.mul(0.8), rc.y, length(ra.xyz.sub(U.camPos))));
  m.maskNode = vFade.lessThan(dither);
  const S = vSize, C = vCol, sd = vSeed;
  // the face's coordinates: u out from the wall (0 at the wall), v up, both in metres
  const u = vL.x.add(S.x.mul(0.5)), v = vL.y;
  const fwv = fwidth(vec2(u, v)), fw = max(max(fwv.x, fwv.y), 1e-4);
  const face = f01(abs(vN.z).greaterThan(0.5));
  const upright = S.y.greaterThan(S.x);
  const rim = float(1).sub(inside(u, 0.08, S.x.sub(0.08), fw).mul(inside(v, 0.08, S.y.sub(0.08), fw)));
  // glyph cells: square, as wide as the board's narrow side less a margin, along its long side
  const cellM = min(S.x, S.y).mul(0.72);
  const along = select(upright, S.y.sub(v), u), across = select(upright, u, v);
  const nCells = max(floor(max(S.x, S.y).sub(0.3).div(cellM.mul(1.08))), 1);
  const start = max(S.x, S.y).sub(nCells.mul(cellM.mul(1.08))).mul(0.5);
  const q = along.sub(start).div(cellM.mul(1.08));
  const gi = floor(q), gv = fract(q).mul(1.08), gu = across.sub(min(S.x, S.y).mul(0.14)).div(cellM);
  const dq = fw.div(cellM);
  const gk = hash(gi.add(sd.mul(57.1)));
  // (strokes cut out of a block, five kinds by the glyph's hash: a slot across, a slot down, two bars, a cross, a counter)
  const slotH = inside(gv, 0.42, 0.56, dq), slotV = inside(gu, 0.42, 0.58, dq);
  const twoBars = inside(gv, 0.26, 0.38, dq).add(inside(gv, 0.62, 0.74, dq)).mul(inside(gu, 0.22, 1, dq));
  const counter = inside(gu, 0.3, 0.7, dq).mul(inside(gv, 0.3, 0.7, dq));
  const cut = select(gk.lessThan(0.18), slotH, select(gk.lessThan(0.36), slotV.mul(inside(gv, 0, 0.8, dq)),
    select(gk.lessThan(0.54), twoBars, select(gk.lessThan(0.72), max(slotH.mul(inside(gu, 0.15, 1, dq)), slotV.mul(inside(gv, 0.2, 1, dq))), counter))));
  const inCell = inside(gu, 0.08, 0.92, dq).mul(inside(gv, 0.06, 0.94, dq)).mul(f01(gi.greaterThan(-0.5).and(gi.lessThan(nCells.sub(0.5)))));
  const res = float(1).sub(smoothstep(float(0.12), float(0.4), dq));
  let glyph = inCell.mul(mix(float(0.45), float(1).sub(min(cut, 1)), res)).mul(f01(gk.lessThan(0.9)));
  // (city.json rooftopLook.signGlyphs "cjk", opt-in; Hong Kong M7, critic c-hk-m4-2: the cut blocks read as Latin
  // letters, four shapes over and over): most boards' glyphs drawn as ink strokes instead, one of 32 per cell by its
  // hash, each on a 5 x 5 stroke grid: two or three horizontal strokes on their own rows and one or two vertical ones,
  // each spanning part of the cell, now and then an enclosure (口) or a narrow left-hand radical; a board in six keeps
  // the block letters (English names). Strokes are 0.13 of the cell; averaged out with the blocks under a few pixels
  if (look.signGlyphs === 'cjk') {
    // (three's hash takes the integer part of its seed: every draw below is its own integer, glyph x 64 + draw)
    const k = floor(gk.mul(32)).mul(64), hk = (n) => hash(k.add(n));
    const row = (n) => floor(hk(n).mul(5)).add(0.5).div(5);
    const bar = (x0, x1, y0, y1) => inside(gu, x0, x1, dq).mul(inside(gv, y0, y1, dq));
    const hStroke = (n) => { const y = row(n), a = hk(n + 1).mul(0.35).add(0.06), b = float(0.94).sub(hk(n + 2).mul(0.35)); return bar(a, b, y.sub(0.065), y.add(0.065)); };
    const vStroke = (n) => { const x = row(n), a = hk(n + 1).mul(0.4).add(0.06), b = float(0.94).sub(hk(n + 2).mul(0.4)); return bar(x.sub(0.065), x.add(0.065), a, b); };
    const box = bar(0.3, 0.84, 0.5, 0.92).mul(float(1).sub(bar(0.43, 0.71, 0.63, 0.79))).mul(f01(hk(30).lessThan(0.3)));
    const radical = bar(0.06, 0.19, 0.08, 0.92).mul(f01(hk(31).lessThan(0.35)));
    const strokes = max(max(max(hStroke(0), hStroke(3)), max(hStroke(6).mul(f01(hk(32).lessThan(0.6))), vStroke(9))),
      max(max(vStroke(12).mul(f01(hk(33).lessThan(0.55))), box), radical));
    const cjk = inCell.mul(mix(float(0.4), min(strokes, 1), res)).mul(f01(gk.lessThan(0.94)));
    glyph = select(hash(sd.mul(71.3)).lessThan(0.84), cjk, glyph);
  }
  if (look.signGlyphs === 'atlas') {
    // (the cell's glyph: x across the character, y down it; upright boards read top-down, wide ones left to right, the
    // far face's x flipped so neither face shows mirrored characters; the mip level from the cell's size on screen,
    // not from the cell-wrapped uv's derivatives)
    // (its own hash of the glyph's index and the board's place (whole metres, under 2^24): the board seed repeated one
    // run of characters on every board)
    const boardId = varying(mod(floor(abs(ra.x)), 997).add(mod(floor(abs(ra.z)), 997).mul(997)));
    const ci = floor(hash(boardId.mul(13).add(gi).add(7)).mul(256));
    const flip = vN.z.lessThan(0);
    const cxu = select(upright, gu, gv), cyv = select(upright, gv, float(1).sub(gu));
    const gx = select(flip, float(1).sub(cxu), cxu).clamp(0, 1), gyv = cyv.clamp(0, 1);
    const auv = vec2(mod(ci, 16).add(gx), floor(ci.div(16)).add(gyv)).div(16);
    const lvl = log2(max(dq.mul(64), 1));
    const mask = texture(signGlyphAtlas(), auv).level(lvl).r;
    const ch = inCell.mul(mix(float(0.35), mask, res)).mul(f01(gk.lessThan(0.97)));
    glyph = select(hash(sd.mul(71.3)).lessThan(0.88), ch, glyph);
  }
  const lum = dot(C, vec3(0.2126, 0.7152, 0.0722));
  const lightBoard = lum.greaterThan(0.35);
  const ink = select(lightBoard, select(sd.lessThan(0.55), vec3(0.55, 0.04, 0.03), vec3(0.03, 0.03, 0.035)),
    select(sd.lessThan(0.6), vec3(0.9, 0.88, 0.82), vec3(0.9, 0.72, 0.1)));
  const rimC = select(sd.greaterThan(0.5), vec3(0.75, 0.75, 0.73), C.mul(0.55));
  const faceC = mix(mix(C, ink, glyph.mul(0.9)), rimC, rim);
  const steel = vec3(0.09, 0.09, 0.1);
  m.colorNode = mix(steel, faceC, face);
  m.roughnessNode = mix(float(0.6), float(0.35), face);
  if (night) {
    const lit = f01(hash(sd.mul(91.7)).lessThan(look.signsLit ?? 0.7)).mul(0.8).add(0.2);
    // (kept under 1 with the tone mapping's shoulder in mind: brighter, the boards bloomed into white blobs and their
    // glyphs and colours went)
    const glow = mix(C.mul(0.5).add(0.01), mix(ink, C, 0.3).mul(0.9).add(0.04), glyph).mul(float(1).sub(rim.mul(0.5)));
    night.withLights(m, glow.mul(face).mul(lit).mul(look.signsGlow ?? 0.9));
  }
  return m;
}

// ---------------------------------------------------------------- the signs' light on the street (opt-in)
// rooftopLook.signSpill { k, reach, along, across } (Hong Kong M8): after dark each lit board's light on the street
// under it, a pool lying on the ground (as lamps.js's), longer along the street than across it (the board's two faces
// look along the street), in the board's colour: Nathan Road's and Sham Shui Po's pavements and roads tinted by their
// signs. Irradiance as from a small lit panel (area A at height h over the ground: A h / (h^2 + d^2)^1.5, the
// paving's albedo folded into k), taken smoothly to nothing at its edge; the lit/dim choice is the board's own (the
// same hash as signMaterial's). Drawn additively without depth writes, only while the lights are on, only for boards
// within `reach` m. Per instance: sa (x, the board's foot y, z, yaw), sb (width out, height, foot over the ground, colour)
const sa = attribute('sa', 'vec4'), sb = attribute('sb', 'vec4');
function spillMaterial(night, look) {
  const S = look.signSpill;
  const m = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false });
  m.name = 'sign-spill';
  m.blending = THREE.AdditiveBlending;
  m.fog = false;
  const k = uniform(S.k ?? 0.6);
  m.userData.uniforms = { k };
  const cy = cos(sa.w), sy = sin(sa.w);
  // the board's height over the ground at its middle, and the pool's half-sizes along the street (the faces' normal,
  // local z) and across it (out from the wall, local x)
  const h = max(sb.z.add(sb.y.mul(0.5)), 1.5);
  const halfZ = h.mul(S.along ?? 1.4).clamp(3, 16), halfX = h.mul(S.across ?? 0.8).clamp(2, 9);
  const corner = attribute('position', 'vec3');           // (a unit quad, x and z in -1..1)
  const lx = corner.x.mul(halfX), lz = corner.z.mul(halfZ);
  m.positionNode = vec3(lx.mul(cy).add(lz.mul(sy)), sb.z.negate().add(S.lift ?? 0.4), lx.mul(sy).negate().add(lz.mul(cy))).add(sa.xyz);
  // the board's own lit choice (signMaterial's: its seed from its position)
  const seed = hash(sa.x.mul(0.731).add(sa.z.mul(1.379)).add(sa.y.mul(0.917)).add(0.5));
  const lit = f01(hash(seed.mul(91.7)).lessThan(look.signsLit ?? 0.7)).mul(0.8).add(0.2);
  const A = sb.x.mul(sb.y);
  const col = varying(unpack(sb.w).mul(lit).mul(A).mul(h));
  const q = varying(vec2(lx, lz)), vh = varying(h), vHalf = varying(vec2(halfX, halfZ));
  const d2 = q.dot(q);
  const e = vh.mul(vh).add(d2).pow(-1.5);
  const t = q.div(vHalf).dot(q.div(vHalf)).clamp(0, 1);
  m.colorNode = vec4(col.mul(e).mul(float(1).sub(t).pow(2)).mul(k).mul(night.lights), 1);
  return m;
}

// a coordinate pair for large-scale noise (metres, offset per item so neighbours differ)
const positionWorldish = (L, sd) => vec2(L.x.mul(0.9).add(sd.mul(97.1)), L.z.mul(0.9).add(L.y.mul(0.7)));

// ---------------------------------------------------------------- data
async function gunzip(buf) {
  const b = new Uint8Array(buf);
  if (b[0] !== 0x1f || b[1] !== 0x8b) return buf;     // a server may already have decoded it
  return new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
}

const linearToSrgb8 = (c) => Math.round(255 * THREE.MathUtils.clamp(c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055, 0, 1));
const packLinear = (r, g, b) => linearToSrgb8(r) * 65536 + linearToSrgb8(g) * 256 + linearToSrgb8(b);

// the distance an item is drawn to, from its size and kind
function reach(sx, sy, sz, mat, M, look = {}) {
  const s = Math.max(sx, sy, sz);
  if (mat === M.sign) return look.signs ?? SIGNS;               // (M.sign: only where the pipeline wrote street signs)
  if (mat === M.pot) return POTS;
  if (mat === M.velux) return SMALL;
  if (mat === M.chimney) return look.stacks ?? STACKS;           // (its height counts the part down to the eaves)
  if (mat === M.helipad || mat === M.pv || mat === M.corrugated || mat === M.parking || s >= 6) return FAR;
  if (s >= 2.5) return BIG;
  if (mat === M.foliage || s < 0.9) return SMALL;
  return MID;
}

// one tile's items: per roof its centre, radius and item range; per item its instance data and prototype
function decodeTile(buf, t, index, M, look, groundAt = null) {
  const u8 = new Uint8Array(buf), dv = new DataView(buf);
  const m = dv.getUint32(0, true), n = dv.getUint32(4, true);
  let off = 8;
  const col16 = (count) => {                       // low bytes, then high bytes -> Uint16Array
    const out = new Uint16Array(count);
    for (let i = 0; i < count; i++) out[i] = u8[off + i] | (u8[off + count + i] << 8);
    off += 2 * count;
    return out;
  };
  const col8 = (count) => { const out = u8.slice(off, off + count); off += count; return out; };
  const s16 = (v) => (v >= 32768 ? v - 65536 : v);
  const dbx = col16(m), dbz = col16(m), dby = col16(m), th = col16(m), cnt = col16(m);
  const kind = col8(n), colr = col8(n), param = col8(n);
  const qa = col16(n), qb = col16(n), dy = col8(n), yaw = col16(n), qsx = col16(n), qsy = col16(n), qsz = col16(n);
  const { item: Q, y: YQ, size: SQ } = index.quant;
  const pal = index.palette.map(([r, g, b]) => packLinear(r, g, b));
  const inst = new Float32Array(n * 10), proto = new Uint8Array(n), lim = new Float32Array(n);
  const roofs = { n: m, x: new Float32Array(m), y: new Float32Array(m), z: new Float32Array(m), r: new Float32Array(m),
    start: new Uint32Array(m), count: new Uint32Array(m), reach: new Float32Array(m) };
  let ax = 0, az = 0, ay = 0, k = 0;
  const TAU = Math.PI * 2;
  for (let j = 0; j < m; j++) {
    ax = (ax + dbx[j]) & 0xffff; az = (az + dbz[j]) & 0xffff; ay = (ay + dby[j]) & 0xffff;
    const cx = t.x + s16(ax) * Q, cz = t.z + s16(az) * Q, y0 = ay * YQ;
    const theta = (th[j] / 65536) * TAU, c = Math.cos(theta), s = Math.sin(theta);
    roofs.x[j] = cx; roofs.z[j] = cz; roofs.y[j] = y0;
    roofs.start[j] = k; roofs.count[j] = cnt[j];
    let r = 0, far = 0;
    for (let e = 0; e < cnt[j]; e++, k++) {
      const a = s16(qa[k]) * Q, b = s16(qb[k]) * Q;
      const x = cx + a * c - b * s, z = cz - (a * s + b * c);
      const sx = qsx[k] * SQ, sy = qsy[k] * SQ, sz = qsz[k] * SQ;
      const mat = kind[k] & 31;
      const o = k * 10;
      inst[o] = x; inst[o + 1] = y0 + dy[k] * YQ; inst[o + 2] = z; inst[o + 3] = theta + (yaw[k] / 65536) * TAU;
      inst[o + 4] = sx; inst[o + 5] = sy; inst[o + 6] = sz; inst[o + 7] = mat + 32 * param[k];
      inst[o + 8] = pal[colr[k]];
      lim[k] = inst[o + 9] = reach(sx, sy, sz, mat, M, look);
      proto[k] = kind[k] >> 5;
      r = Math.max(r, Math.hypot(a, b) + 0.5 * Math.hypot(sx, sz));
      far = Math.max(far, lim[k]);
    }
    roofs.r[j] = r;
    roofs.reach[j] = far;
  }
  // (rooftopLook.signSpill: the ground under each street sign, for its light's pool on the street)
  let gy = null;
  if (groundAt && M.sign !== undefined) {
    gy = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      if ((inst[i * 10 + 7] % 32) !== M.sign) continue;
      const g = groundAt(inst[i * 10], inst[i * 10 + 2]);
      gy[i] = Number.isFinite(g) ? g : inst[i * 10 + 1] - 4;
    }
  }
  return { roofs, inst, proto, lim, n, gy };
}

// ---------------------------------------------------------------- parapets from the building tiles
// A wall's top edge is where its triangle has two corners at the building's top: its base (TEXCOORD_2.x, the
// ground it stands on) plus its height (TEXCOORD_1.y); each wall quad has exactly one such triangle. Style
// ids and seeds come from TEXCOORD_1.x as in facade.js.
function parapetsOf(group, tilesIndex, parapetKinds, M, landmarks) {
  let mesh = null;
  group.traverse((o) => { if (o.isMesh && o.geometry.attributes.uv1) mesh = o; });
  if (!mesh) return { n: 0, inst: new Float32Array(0) };
  mesh.updateWorldMatrix(true, false);
  const g = mesh.geometry, pos = g.attributes.position, nrm = g.attributes.normal, colA = g.attributes.color;
  const fac = g.attributes.uv1, baseA = g.attributes.uv2, index = g.index;
  const e = mesh.matrixWorld.elements;
  const [facS, facH] = tilesIndex.uvRange.fac;
  const baseR = tilesIndex.uvRange.base?.[0] ?? 0;
  const walls = [];                                   // every wall's top edge: x0, z0, x1, z1, nx, nz, H, style, seed, colour
  const P = [0, 0, 0].map(() => new THREE.Vector3());
  for (let t = 0; t < index.count; t += 3) {
    const i0 = index.getX(t);
    if (Math.abs(nrm.getY(i0)) > 0.3) continue;
    const H = fac.getY(i0) * facH, top0 = H + (baseA ? baseA.getX(i0) * baseR : 0);
    const top = [];
    for (let c = 0; c < 3; c++) {
      const i = index.getX(t + c);
      P[c].set(pos.getX(i) * e[0] + e[12], pos.getY(i) * e[5] + e[13], pos.getZ(i) * e[10] + e[14]);
      if (Math.abs(P[c].y - top0) < 0.15) top.push(P[c]);
    }
    if (top.length !== 2) continue;
    // a wall under a roof shape (a mansard's or pitched roof's party wall, 06_tiles.py ROOF) carries no parapet
    const roofCode = baseA ? baseA.getY(i0) * (tilesIndex.uvRange.base?.[1] ?? 0) + 0.001 : 0;
    if (roofCode - 8 * Math.floor(roofCode / 8) - 0.001 > 0.05) continue;
    const code = fac.getX(i0) * facS + 0.0005, style = Math.floor(code), seed = (code - style) / 0.999;
    walls.push([top[0].x, top[0].z, top[1].x, top[1].z, nrm.getX(i0), nrm.getZ(i0), top0, style, seed,
      packLinear(colA.getX(i0), colA.getY(i0), colA.getZ(i0)), H]);
  }
  // spatial hash of the edges, to find walls standing back to back with another building's
  const CELL = 6, grid = new Map();
  const keyOf = (x, z) => `${Math.floor(x / CELL)},${Math.floor(z / CELL)}`;
  walls.forEach((w, i) => {
    const L = Math.hypot(w[2] - w[0], w[3] - w[1]), steps = Math.max(1, Math.ceil(L / CELL));
    const seen = new Set();
    for (let s = 0; s <= steps; s++) {
      const k = keyOf(w[0] + ((w[2] - w[0]) * s) / steps, w[1] + ((w[3] - w[1]) * s) / steps);
      if (seen.has(k)) continue;
      seen.add(k);
      if (!grid.has(k)) grid.set(k, []);
      grid.get(k).push(i);
    }
  });
  const covered = (w) => {
    const mx = (w[0] + w[2]) / 2, mz = (w[1] + w[3]) / 2;
    for (const j of grid.get(keyOf(mx, mz)) ?? []) {
      const o = walls[j];
      if (o === w || w[4] * o[4] + w[5] * o[5] > -0.9 || o[6] < w[6] - 1.5) continue;
      // o's line: distance of our midpoint to it, and whether it projects within o
      const dx = o[2] - o[0], dz = o[3] - o[1], L2 = dx * dx + dz * dz;
      if (L2 < 1e-4) continue;
      const t = ((mx - o[0]) * dx + (mz - o[1]) * dz) / L2;
      const px = o[0] + t * dx - mx, pz = o[1] + t * dz - mz;
      if (t > -0.05 && t < 1.05 && px * px + pz * pz < 0.36) return true;
    }
    return false;
  };
  const inLandmark = (x, z) => landmarks.some((lm) => x >= lm.x0 && x <= lm.x1 && z >= lm.z0 && z <= lm.z1 && pointIn(lm.pts, x, z));
  const out = [];
  const concrete = packLinear(0.6, 0.59, 0.56);
  for (const w of walls) {
    const [x0, z0, x1, z1, nx, nz, top, style, seed, colour, H] = w;
    const kind = parapetKind(parapetKinds[style], seed, H);
    if (!kind) continue;
    const L = Math.hypot(x1 - x0, z1 - z0);
    if (L < 0.3) continue;
    const mx = (x0 + x1) / 2, mz = (z0 + z1) / 2;
    if (inLandmark(mx - nx * 0.8, mz - nz * 0.8) || covered(w)) continue;
    // box along the edge, its local +z pointing into the roof (away from the wall's outward normal)
    let yaw = Math.atan2(-(z1 - z0), x1 - x0);
    const ezx = Math.sin(yaw), ezz = Math.cos(yaw);
    if (ezx * nx + ezz * nz > 0) yaw += Math.PI;
    const [h, th, glass] = kind;
    out.push(mx - nx * th / 2, top, mz - nz * th / 2, yaw, L, h, th,
      (glass === 1 ? M.screen : M.parapet), glass === 2 ? concrete : colour, glass === 1 ? BIG : MID);
  }
  return { n: out.length / 10, inst: Float32Array.from(out) };
}

function pointIn(pts, x, z) {
  let c = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, zi] = pts[i], [xj, zj] = pts[j];
    if ((zi > z) !== (zj > z) && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) c = !c;
  }
  return c;
}

// [height, thickness, glass (0 wall, 1 glass screen, 2 wall of light concrete)] of a building's parapet,
// or null; the choices follow the building's seed, so every wall of a building agrees. kind: the style's parapet
// (styles.js `parapet`): village, block (apartment towers, malls, civic buildings), low (Paris's flat roofs, europe-west:
// low rendered acrotères on post-war, panel, modern and HBM blocks), glass, factory; none (plant rooms and landmark
// styles): null
function parapetKind(kind, seed, H) {
  const r = (k) => { const v = Math.sin(seed * 12.9898 * k + 4.1) * 43758.5453; return v - Math.floor(v); };
  switch (kind) {
    case 'village': return [0.9 + 0.35 * r(1), 0.2, 0];
    case 'block': return [1.1 + 0.4 * r(1), 0.25, 0];
    case 'low': return [0.6 + 0.5 * r(1), 0.25, 0];
    case 'glass': return r(2) < 0.55 ? [1.8 + 1.6 * r(1), 0.3, 1] : [1.2 + 0.4 * r(1), 0.3, 2];
    case 'factory':
      if (H >= 12) return [0.9 + 0.3 * r(1), 0.25, 0];
      return r(2) < 0.35 ? [0.5 + 0.3 * r(1), 0.2, 0] : null;
    default: return null;
  }
}

// ---------------------------------------------------------------- the module
// styles: the facade styles' data by name (styles.js resolveStyles), whose `parapet` gives each style's parapets
// night: night.js's uniforms (the street signs' lights; unused without signs)
export async function createRooftops({ scene, camera, invalidate, tileGroups, tilesIndex, terrain = null, url = 'rooftops/', look = {}, styles = {}, night = null }) {
  const index = await fetch(url + 'rooftops.json', { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (!index) return null;
  const M = Object.fromEntries(index.materials.map((name, i) => [name, i]));
  // (each style id's parapet kind, by rooftops.json's style names, the tiles' order)
  const parapetKinds = index.styles.map((name) => styles[name]?.parapet ?? null);
  const landmarks = index.landmarks.map((pts) => {
    const xs = pts.map((p) => p[0]), zs = pts.map((p) => p[1]);
    return { pts, x0: Math.min(...xs), x1: Math.max(...xs), z0: Math.min(...zs), z1: Math.max(...zs) };
  });
  const group = new THREE.Group();
  group.name = 'rooftops';
  scene.add(group);

  // instanced meshes: one per prototype, plus the parapets (boxes)
  const pick = (names) => Object.fromEntries(names.map((n) => [n, M[n]]));
  const kinds = [
    { name: 'box', geo: boxGeometry(), mats: pick(['concrete', 'stair', 'hvac', 'cooling', 'paneltank', 'steel', 'skylight', 'green', 'helipad', 'parking', 'car', 'chimney', 'velux', 'zinc']), shadow: true },
    { name: 'cylinder', geo: cylinderGeometry(), mats: pick(['stainless', 'plastic', 'turbine', 'cooling', 'wood']), shadow: true },
    { name: 'panel', geo: panelGeometry(), mats: pick(['tubes', 'pv', 'corrugated']), shadow: true },
    { name: 'gable', geo: gableGeometry(), mats: pick(['tile', 'skylight']), shadow: true },
    { name: 'blob', geo: blobGeometry(), mats: pick(['foliage']), shadow: false },
    { name: 'cone', geo: coneGeometry(), mats: pick(['wood', 'stainless']), shadow: true },
    ...(M.pot !== undefined ? [{ name: 'pots', geo: potsGeometry(), mats: pick(['pot']), shadow: false }] : []),
    // (street signs, Hong Kong's: the prototype after the shared ones, its own material, lit after dark)
    ...(M.sign !== undefined ? [{ name: 'sign', geo: boxGeometry(), mats: pick(['sign']), shadow: true }] : []),
    { name: 'parapet', geo: boxGeometry(), mats: pick(['parapet', 'screen']), shadow: true },
  ];
  const meshes = kinds.map((k) => {
    const mesh = new THREE.Mesh(new THREE.InstancedBufferGeometry(), k.name === 'sign' ? signMaterial(night, look) : rooftopMaterial(k.name, k.mats, look));
    mesh.frustumCulled = false;
    mesh.visible = false;
    mesh.castShadow = k.shadow;
    mesh.receiveShadow = true;
    mesh.name = `rooftops-${k.name}`;
    mesh.userData = { base: k.geo, cap: 0, n: 0, ra: null, rb: null, rc: null, tris: k.geo.index.count / 3 };
    group.add(mesh);
    return mesh;
  });
  const PARAPET = meshes.length - 1;
  // (rooftopLook.signSpill, opt-in: the lit signs' light on the street, an additive pool per board near the camera)
  const SIGN = kinds.findIndex((k) => k.name === 'sign');
  let spill = null;
  if (look.signSpill && SIGN >= 0 && night && terrain) {
    const quad = new THREE.BufferGeometry();
    quad.setAttribute('position', new THREE.Float32BufferAttribute([-1, 0, -1, 1, 0, -1, 1, 0, 1, -1, 0, 1], 3));
    quad.setIndex([0, 2, 1, 0, 3, 2]);
    spill = new THREE.Mesh(new THREE.InstancedBufferGeometry(), spillMaterial(night, look));
    spill.name = 'rooftops-sign-spill';
    spill.frustumCulled = false;
    spill.visible = false;
    spill.renderOrder = 2;
    spill.castShadow = spill.receiveShadow = false;
    spill.userData = { base: quad, cap: 0, n: 0, sa: null, sb: null, reach: look.signSpill.reach ?? 450 };
    group.add(spill);
  }
  const gyOf = new WeakMap();
  function ensureSpill(n) {
    const u = spill.userData;
    if (n <= u.cap) return;
    u.cap = Math.ceil((n * 1.5) / 1024) * 1024;
    const g = new THREE.InstancedBufferGeometry();
    g.setAttribute('position', u.base.attributes.position);
    g.setIndex(u.base.index);
    u.sa = new THREE.InstancedBufferAttribute(new Float32Array(u.cap * 4), 4);
    u.sb = new THREE.InstancedBufferAttribute(new Float32Array(u.cap * 4), 4);
    for (const a of [u.sa, u.sb]) a.setUsage(THREE.DynamicDrawUsage);
    g.setAttribute('sa', u.sa);
    g.setAttribute('sb', u.sb);
    spill.geometry.dispose();
    spill.geometry = g;
  }
  function ensure(mesh, n) {
    const u = mesh.userData;
    if (n <= u.cap) return;
    u.cap = Math.ceil((n * 1.5) / 1024) * 1024;
    const g = new THREE.InstancedBufferGeometry();
    for (const k of Object.keys(u.base.attributes)) g.setAttribute(k, u.base.attributes[k]);
    g.setIndex(u.base.index);
    u.ra = new THREE.InstancedBufferAttribute(new Float32Array(u.cap * 4), 4);
    u.rb = new THREE.InstancedBufferAttribute(new Float32Array(u.cap * 4), 4);
    u.rc = new THREE.InstancedBufferAttribute(new Float32Array(u.cap * 2), 2);
    for (const a of [u.ra, u.rb, u.rc]) a.setUsage(THREE.DynamicDrawUsage);
    g.setAttribute('ra', u.ra);
    g.setAttribute('rb', u.rb);
    g.setAttribute('rc', u.rc);
    mesh.geometry.dispose();
    mesh.geometry = g;
  }

  // tiles: items loaded when within reach and dropped well out of it; parapets built from the building tile
  const tiles = index.tiles.map((t) => ({ ...t, state: 'idle', data: null, parapets: null,
    key: t.file.replace(/^r_/, 't_').replace(/\.bin$/, '.glb') }));
  const byKey = new Map(tiles.map((t) => [t.key, t]));
  // building tiles without items can still carry parapets
  for (const bt of tilesIndex.tiles) {
    if (!byKey.has(bt.file)) {
      const t = { file: null, x: bt.x, z: bt.z, maxHeight: bt.maxHeight, state: 'ready', data: null, parapets: null, key: bt.file };
      tiles.push(t);
      byKey.set(bt.file, t);
    }
  }
  let inflight = 0, needFill = true, groupsSeen = 0;
  // (the camera's height above the ground under it counts, not above the sea)
  let camGround = 0;
  const tileDist2 = (t, p) => {
    const dx = Math.max(t.x - p.x, 0, p.x - t.x - 1000), dz = Math.max(t.z - p.z, 0, p.z - t.z - 1000);
    const dy = Math.max(p.y - camGround, 0);
    return dx * dx + dz * dz + dy * dy;
  };
  async function load(t) {
    t.state = 'loading';
    inflight++;
    try {
      const buf = await gunzip(await (await fetch(url + t.file)).arrayBuffer());
      if (t.state === 'loading') {
        t.data = decodeTile(buf, t, index, M, look, spill ? terrain.height : null);
        if (t.data.gy) gyOf.set(t.data.inst, t.data.gy);
        t.state = 'ready';
      }
    } catch (e) {
      console.warn('rooftops: tile failed', t.file, e);
      t.state = 'failed';
    }
    inflight--;
    needFill = true;
    invalidate({ shadows: true, redraw: true });   // (an arrival, not a move: see main.js)
  }
  function stream(p) {
    const want = [];
    for (const t of tiles) {
      if (!t.file) continue;
      const d2 = tileDist2(t, p);
      if (t.state === 'idle' && d2 < (FAR + 300) ** 2) want.push([d2, t]);
      else if ((t.state === 'ready' || t.state === 'loading') && d2 > (FAR + 2500) ** 2) {
        t.state = 'idle';
        t.data = null;
      }
    }
    want.sort((a, b) => a[0] - b[0]);
    for (const [, t] of want) {
      if (inflight >= CONCURRENCY) break;
      load(t);
    }
  }
  const groupOf = new Map();
  function parapets(t) {
    if (t.parapets) return t.parapets;
    if (groupsSeen !== tileGroups.length) {
      for (const g of tileGroups) if (g.userData.tile?.file) groupOf.set(g.userData.tile.file, g);
      groupsSeen = tileGroups.length;
    }
    const g = groupOf.get(t.key);
    if (!g) return null;                               // its building tile hasn't arrived yet
    const near = landmarks.filter((lm) => lm.x1 > t.x - 50 && lm.x0 < t.x + 1050 && lm.z1 > t.z - 50 && lm.z0 < t.z + 1050);
    t.parapets = parapetsOf(g, tilesIndex, parapetKinds, M, near);
    return t.parapets;
  }

  // refill the instance buffers from the tiles near and in view
  const frustum = new THREE.Frustum(), projView = new THREE.Matrix4(), box = new THREE.Box3(), sphere = new THREE.Sphere();
  const stats = { items: 0, parapets: 0, tiles: 0, triangles: 0, draws: 0 };
  const counts = new Array(meshes.length).fill(0);
  function fill() {
    const p = camera.position;
    camera.updateMatrixWorld();
    projView.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    frustum.setFromProjectionMatrix(projView, camera.coordinateSystem, camera.reversedDepth);   // (the camera's own depth convention)
    const list = [];
    let pending = false;
    for (const t of tiles) {
      if (tileDist2(t, p) > FAR ** 2) continue;
      box.min.set(t.x - 150, 0, t.z - 150);
      box.max.set(t.x + 1150, (t.maxHeight ?? 300) + 10, t.z + 1150);
      if (!frustum.intersectsBox(box)) continue;
      const withParapets = tileDist2(t, p) < BIG ** 2;
      if (withParapets && !parapets(t)) pending = true;
      list.push([t, withParapets]);
    }
    // pass 1: pick what is drawn (per roof: in view and within reach), counting per mesh
    counts.fill(0);
    const picked = [];
    for (const [t, withParapets] of list) {
      const d = t.data;
      if (d) {
        const R = d.roofs;
        for (let j = 0; j < R.n; j++) {
          const dx = R.x[j] - p.x, dz = R.z[j] - p.z, dy = R.y[j] - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) - R.r[j];
          if (dist > R.reach[j]) continue;
          sphere.center.set(R.x[j], R.y[j] + 3, R.z[j]);
          sphere.radius = R.r[j] + 6;
          if (!frustum.intersectsSphere(sphere)) continue;
          for (let k = R.start[j], e = k + R.count[j]; k < e; k++) {
            if (dist > d.lim[k]) continue;
            picked.push(d.inst, k, d.proto[k]);
            counts[d.proto[k]]++;
          }
        }
      }
      const pp = withParapets && t.parapets;
      if (pp && pp.n) {
        const I = pp.inst;
        for (let k = 0; k < pp.n; k++) {
          const o = k * 10;
          const dx = I[o] - p.x, dz = I[o + 2] - p.z, dy = I[o + 1] - p.y;
          if (dx * dx + dy * dy + dz * dz > I[o + 9] * I[o + 9]) continue;
          picked.push(I, k, PARAPET);
          counts[PARAPET]++;
        }
      }
    }
    meshes.forEach((mesh, j) => { ensure(mesh, counts[j]); mesh.userData.n = 0; });
    // pass 2: write
    for (let q = 0; q < picked.length; q += 3) {
      const I = picked[q], o = picked[q + 1] * 10, u = meshes[picked[q + 2]].userData;
      const k = u.n++;
      u.ra.array.set(I.subarray(o, o + 4), k * 4);
      u.rb.array.set(I.subarray(o + 4, o + 8), k * 4);
      u.rc.array[k * 2] = I[o + 8];
      u.rc.array[k * 2 + 1] = I[o + 9];
    }
    if (spill) {
      const R2 = spill.userData.reach ** 2;
      let c = 0;
      for (let q = 0; q < picked.length; q += 3) {
        if (picked[q + 2] !== SIGN) continue;
        const I = picked[q], o = picked[q + 1] * 10;
        const dx = I[o] - p.x, dz = I[o + 2] - p.z;
        if (dx * dx + dz * dz < R2) c++;
      }
      ensureSpill(c);
      const u = spill.userData;
      u.n = 0;
      for (let q = 0; q < picked.length && u.sa; q += 3) {
        if (picked[q + 2] !== SIGN) continue;
        const I = picked[q], i = picked[q + 1], o = i * 10;
        const dx = I[o] - p.x, dz = I[o + 2] - p.z;
        if (dx * dx + dz * dz >= R2) continue;
        // (the data's ground: the tile's, found by the item's array)
        const gy = gyOf.get(I)?.[i] ?? I[o + 1] - 4;
        const k = u.n++;
        u.sa.array.set([I[o], I[o + 1], I[o + 2], I[o + 3]], k * 4);
        u.sb.array.set([I[o + 4], I[o + 5], Math.max(0, I[o + 1] - gy), I[o + 8]], k * 4);
      }
      if (u.sa) {
        spill.geometry.instanceCount = u.n;
        for (const a of [u.sa, u.sb]) { a.clearUpdateRanges(); a.addUpdateRange(0, Math.max(1, u.n * 4)); a.needsUpdate = true; }
      }
    }
    stats.triangles = stats.draws = stats.items = 0;
    for (const mesh of meshes) {
      const u = mesh.userData;
      mesh.visible = u.n > 0;
      if (mesh.visible) { stats.draws++; stats.triangles += u.n * u.tris; }
      if (mesh !== meshes[PARAPET]) stats.items += u.n;
      if (!u.ra) continue;
      mesh.geometry.instanceCount = u.n;
      for (const a of [u.ra, u.rb, u.rc]) {
        a.clearUpdateRanges();
        a.addUpdateRange(0, Math.max(1, u.n * a.itemSize));
        a.needsUpdate = true;
      }
    }
    stats.parapets = meshes[PARAPET].userData.n;
    stats.tiles = list.length;
    return pending;
  }

  const lastPos = new THREE.Vector3(Infinity, 0, 0), lastQuat = new THREE.Quaternion();
  let lastFill = 0;
  function update(moving) {
    if (!group.visible) return;
    if (spill) spill.visible = spill.userData.n > 0 && night.lights.value > 0;
    const p = camera.position;
    U.camPos.value.copy(p);
    camGround = terrain ? terrain.height(p.x, p.z) : 0;
    stream(p);
    const moved = p.distanceTo(lastPos) > Math.max(8, 0.03 * (p.y - camGround));
    const turned = camera.quaternion.angleTo(lastQuat) > 0.04;
    const now = performance.now();
    if (!(needFill || moved || turned) || (moving && now - lastFill < REFILL_MS)) return;
    needFill = fill();                   // true while some building tiles in view haven't arrived
    if (needFill) setTimeout(() => invalidate({ redraw: true }), 400);
    lastFill = now;
    lastPos.copy(p);
    lastQuat.copy(camera.quaternion);
  }
  // the parapets of a building tile worked out now, before main.js drops the tile's arrays from the page's memory
  // (once they are on the GPU): made later, when the view came within reach, they found empty arrays, and tiles
  // loaded away from the start view had none. False if its group isn't in yet
  function prepareParapets(file) {
    const t = byKey.get(file);
    return !t || !!parapets(t);
  }
  return { group, update, stats, meshes, index, tiles, prepareParapets, spill };
}
