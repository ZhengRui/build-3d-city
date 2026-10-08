// Trees: street trees, woods, parks and courtyards (08_trees.py).
//
// Placement: street trees arrive as points; everything else as a class raster per 1 km tile (forest, park,
// orchard, ...), which this module scatters trees over on a jittered grid with each class's own spacing,
// density, heights and species mix (CLASS below; city.json's trees.classes changes any of it).
//
// Look: trees are built the way real-time foliage usually is, not as solid lumps. Seven species, chosen for
// Shenzhen (another climate wants species of its own here): banyan (wide, dense, dark), camphor-like round broadleaves, open olive acacias, flowering
// Bauhinia / flame trees, low mangroves, royal palms and leaning coconut palms.
//   leaf atlas   drawn on a canvas at startup: twig clusters of a few thousand leaves in sprays (small
//                ficus leaves, rounder camphor leaves, narrow acacia phyllodes, blossom, mangrove) and a
//                pinnate palm frond. The atlas holds no colour, only leaf brightness (each leaf's lit and
//                shaded half, spray tips lighter, bases in shade), a blossom mask and a hue jitter; the
//                tree's own colour comes per instance, so one atlas serves every tree. Its mipmaps keep the
//                alpha-tested coverage, so crowns don't thin out with distance.
//   near trees   (< NEAR m) per species: a crown of 50-90 camera-facing leaf-cluster cards arranged in
//                lobes, alpha tested (alpha to coverage under MSAA), over a trunk and a limb to each lobe
//                that show through the gaps (banyans also drop aerial roots). Card normals point out of
//                their lobe and the crown (spherical normals), so a crown shades as a soft clumpy volume;
//                cards deep inside and under it are darker (baked occlusion). Leaves glow when seen against
//                the sun. Palms are rigid: a grey column, arched fronds folded along the rachis.
//   impostors    (NEAR .. FAR m) each species is rendered at startup from nine elevations (0-90 degrees)
//                and two azimuths into an atlas of brightness/blossom/part and normals (read back and
//                mipmapped on the CPU); a far tree is one camera-facing quad showing the frame nearest its
//                elevation, mirrored or not, lit with the baked normals, so it matches the near tree in
//                colour and silhouette. Near and impostor cross-fade by screen-door dithering.
// Shadows: near cards turn to face the sun in the shadow pass, impostors show the sun their sun-elevation
// frame; both look their shadows up a little sunwards so a crown isn't blotched by itself at shadow-map
// resolution (its lit and shaded sides come from the normals), while buildings and other trees still
// shade it. In woods the crowns' shadows on each other and on the floor are much of the canopy's texture.
// Beyond FAR the carpet (wooded areas as flat polygons, one draw call) stands in for the forest; from about
// a kilometre it also lies under closed stands as their dark floor.
//
// Draw calls: one per species near (7) plus one for all impostors. Per instance the GPU gets 6 floats
// (x, z, height, crown width, packed sRGB colour, species).
import * as THREE from 'three/webgpu';
import {
  attribute, uniform, vec2, vec3, vec4, float, cos, sin, mix, normalize, floor, fract, pow, hash, max,
  mx_noise_float, smoothstep, clamp, asin, cross, dot, length, texture, varying, select, screenCoordinate,
  transformNormalToView, positionWorld, normalWorld, uv, vertexColor, saturate, step, mx_worley_noise_float, cameraPosition, Fn, If, exp,
} from 'three/tsl';

const NEAR = 280, FADE = 45;          // full trees within NEAR m, dissolving into impostors over the last FADE m
let FAR = 4500;                       // no trees beyond (the carpet); the last FAR_FADE m dissolve
let FAR_FADE = 600;                   // (both: city.json trees.carpetBlend, opt-in; these by default)
const SELF_SHADOW = 0.8;              // shadow lookups move this many crown radii towards the sun
const THIN_FROM = 1300;               // dense stands thin out beyond this
const CARPET_Y = 0.8;                 // above the green ground layer (0.6), below water (0.9) and roads
let TRUNK_DROP = 0;                   // (city.json trees.trunkDrop: see nearMaterial)
let CARPET_BRANCH = false;            // (city.json trees.carpetBranch: see loadCarpet)
let CARPET_NORMALS = false;           // (city.json trees.carpetNormals: see loadCarpet)
// (city.json trees.uplight { k, h, colour }, opt-in, Singapore M8 fix round 1: after dark the near crowns' undersides lit
// by the street lamps below them, brightest low down and fading over h m above the ground; lights: night.js's
// lampLights, given by main.js. Absent: no node, the crowns black at night as before)
let UPLIGHT = null;
let BLEND = null;                     // (city.json trees.carpetBlend: see createTrees and loadCarpet)
const SINK = 0.3;                     // trees stand this far into the ground: the ground layers' 16 bit
                                      // positions put them up to a few cm off the terrain on steep slopes
const CONCURRENCY = 4;

// ---------------------------------------------------------------- species
// Canonical size (h, crown radius R, metres) is what the model is built at and the impostor rendered at;
// each tree scales it to its own height and width (R = w / 2 * wK). Colours are sRGB palettes of the
// leaves' base albedo; the leaf atlas modulates it.
const SPECIES = [
  { name: 'banyan', h: 11, R: 7, wK: 1.15, trunkK: 1.35, bark: '#5c5850',      // Ficus microcarpa: dense, wide
    pal: ['#304a2c', '#36522f', '#3b5a33', '#2c4529', '#415f36', '#375332'] },
  { name: 'camphor', h: 12, R: 5.2, wK: 1.0, trunkK: 1.25, bark: '#4d463d',   // camphor, mango, longan: round
    pal: ['#4d6b33', '#567538', '#5f7e3e', '#496535', '#668544', '#526f36'] },
  { name: 'acacia', h: 12, R: 4.6, wK: 0.95, trunkK: 1.0, bark: '#5a534b',    // Acacia, eucalyptus: open, olive
    pal: ['#4b5a38', '#54633c', '#48583b', '#5b6a41', '#505f40'] },
  { name: 'bloom', h: 9, R: 4.8, wK: 1.05, trunkK: 1.1, bark: '#5a5047', bloom: true,   // Bauhinia, flame tree
    pal: ['#45632f', '#4d6b35', '#55733c'] },
  { name: 'mangrove', h: 4.5, R: 3.2, wK: 1.0, trunkK: 0.8, bark: '#3f3a33',  // low, dense, dark
    pal: ['#344830', '#3a4f33', '#32452e', '#3e5436'] },
  { name: 'royal', h: 16, R: 4.3, palm: true, bark: '#9d998f',                // royal palm: grey column
    pal: ['#4a6630', '#527035', '#445e2d', '#58763a'] },
  { name: 'coconut', h: 13, R: 5, palm: true, bark: '#8a8072',                // coconut palm: leaning, drooping
    pal: ['#566f38', '#5e793c', '#4f6834', '#64803f'] },
];
let SP = Object.fromEntries(SPECIES.map((s, i) => [s.name, i]));
const BLOOM = ['#b4508e', '#a2468a', '#c43c2c', '#cf5a34'];   // purple Bauhinia, flame tree red

// per class in trees.json: grid step (m), chance a grid cell holds a tree, height range (m), crown width
// as a share of height, species weights, clumping (0: even, 1: groves and clearings), brightness, thinned far
const URBAN = { banyan: 0.42, camphor: 0.33, acacia: 0.08, bloom: 0.1, royal: 0.05, coconut: 0.02 };
// (Shenzhen's; city.json's trees.classes replaces any class's values, and adds classes)
const CLASS = {
  forest: { step: 7.5, p: 0.93, h: [8, 16], wr: [0.7, 1.0], mix: { acacia: 0.4, camphor: 0.35, banyan: 0.25 },
    clump: 0.25, tone: 1, thin: true },
  park: { step: 9, p: 0.6, h: [6, 13], wr: [0.7, 1.0], mix: { banyan: 0.36, camphor: 0.3, acacia: 0.08, bloom: 0.1,
    royal: 0.1, coconut: 0.06 }, clump: 0.8, tone: 1, thin: true },
  orchard: { step: 7, p: 0.85, h: [4, 7], wr: [0.9, 1.2], mix: { camphor: 1 }, clump: 0.2, tone: 0.85, thin: true },
  mangrove: { step: 5.5, p: 0.9, h: [3, 6], wr: [1.1, 1.5], mix: { mangrove: 1 }, clump: 0.4, tone: 1, thin: true },
  scrub: { step: 7, p: 0.45, h: [2.5, 5], wr: [1.0, 1.4], mix: { mangrove: 0.5, acacia: 0.5 }, clump: 0.7, tone: 1.1,
    thin: true },
  grass: { step: 13, p: 0.08, h: [6, 12], wr: [0.8, 1.1], mix: URBAN, clump: 1, tone: 1 },
  residential: { step: 9, p: 0.4, h: [6, 12], wr: [0.7, 1.0], mix: { ...URBAN, royal: 0.12 }, clump: 0.6, tone: 1 },
  campus: { step: 10, p: 0.28, h: [7, 13], wr: [0.7, 1.0], mix: { ...URBAN, royal: 0.08 }, clump: 0.6, tone: 1 },
  industrial: { step: 12, p: 0.1, h: [6, 11], wr: [0.7, 1.0], mix: URBAN, clump: 0.8, tone: 1 },
  open: { step: 11, p: 0.14, h: [5, 11], wr: [0.7, 1.0], mix: URBAN, clump: 0.9, tone: 1 },
};
// the classes with a city's own values over CLASS, species weights made cumulative: [species, upper bound]
function classTable(own = {}) {
  const out = {};
  for (const name of new Set([...Object.keys(CLASS), ...Object.keys(own)])) {
    const c = out[name] = { ...CLASS[name], ...own[name] };
    const tot = Object.values(c.mix).reduce((a, b) => a + b, 0);
    let acc = 0;
    c.cum = Object.entries(c.mix).map(([k, w]) => [SP[k], (acc += w / tot)]);
  }
  return out;
}
// the carpet: the canopy colour of each wooded class as seen from afar
let DENSE = new Set(['forest', 'mangrove', 'orchard']);     // closed stands: dark floor under the trees (city.json trees.dense)
const CARPET = { forest: '#2b4128', park: '#324d2c', orchard: '#3a532e', mangrove: '#33472f', scrub: '#4c5a37' };

// ---------------------------------------------------------------- small helpers
const hash2 = (a, b, c = 0) => {                      // integers -> [0, 1)
  let h = Math.imul(a | 0, 0x27d4eb2d) ^ Math.imul(b | 0, 0x165667b1) ^ Math.imul(c | 0, 0x9e3779b1);
  h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
};
const smooth = (t) => t * t * (3 - 2 * t);
function vnoise2(x, y, seed = 0) {                    // value noise in [0, 1]
  const xi = Math.floor(x), yi = Math.floor(y), fx = smooth(x - xi), fy = smooth(y - yi);
  const a = hash2(xi, yi, seed), b = hash2(xi + 1, yi, seed), c = hash2(xi, yi + 1, seed), d = hash2(xi + 1, yi + 1, seed);
  return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
}
function rng(seed) {                                  // mulberry32
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const clamp01 = (x) => Math.min(1, Math.max(0, x));
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const packColor = (c, k) => {                         // sRGB 0..1 * brightness -> 24-bit integer
  const r = Math.min(255, Math.round(c.r * k * 255)), g = Math.min(255, Math.round(c.g * k * 255)),
    b = Math.min(255, Math.round(c.b * k * 255));
  return r * 65536 + g * 256 + b;
};
// THREE.Color parses hex as sRGB and stores linear; convert back so packed values are sRGB bytes
const sRGB = (hex) => new THREE.Color(hex).convertLinearToSRGB();
let PALC = SPECIES.map((s) => s.pal.map(sRGB));
const treeColor = (sp, u, k) => packColor(PALC[sp][Math.floor(u * PALC[sp].length) % PALC[sp].length], k);

// ---------------------------------------------------------------- leaf atlas
// 1024 x 1024, 4 x 4 tiles of 256 px; tile 14-15 together hold the palm frond (512 x 256, base at the left).
// Channels: R leaf brightness, G blossom mask, B hue jitter (0.5 neutral), A coverage. Data row 0 is v = 0.
const ATLAS = 1024, TILE = 256;
const TILES = { banyan: [0, 1, 2, 3], camphor: [4, 5, 6, 7], acacia: [8, 9], bloom: [10, 11], mangrove: [12, 13] };
const FROND = 14;
const CARD_UV = 0.42;             // cards map the middle 84% of a tile
const LEAF = {   // leaf length and width (px; a tile is a 3-4 m card), leaves and sprays per tile, hue spread
  banyan: { L: 7, W: 3.6, n: 5200, sprays: [36, 44], size: 0.13, spread: 1, hue: 0.07 },
  camphor: { L: 8, W: 4.5, n: 4400, sprays: [32, 40], size: 0.14, spread: 1, hue: 0.12 },
  acacia: { L: 13, W: 2, n: 3600, sprays: [26, 32], size: 0.15, spread: 0.95, hue: 0.1 },
  bloom: { L: 8, W: 4.5, n: 4000, sprays: [30, 38], size: 0.14, spread: 1, hue: 0.08, flowers: 260 },
  mangrove: { L: 7, W: 4, n: 5200, sprays: [36, 44], size: 0.13, spread: 1, hue: 0.06 },
};
const rgb = (r, g, b) => `rgb(${Math.round(clamp01(r) * 255)},${Math.round(clamp01(g) * 255)},${Math.round(clamp01(b) * 255)})`;

// A twig cluster: sprays of leaves radiating from the middle of the tile, each an elongated tuft whose
// upper, outer leaves catch the light and whose base is in shade, on thin dark twigs
function drawCluster(ctx, ox, oy, o, rnd) {
  const S = TILE, cx = ox + S / 2, cy = oy + S / 2;
  const nc = o.sprays[0] + Math.floor(rnd() * (o.sprays[1] - o.sprays[0] + 1));
  const sprays = [];
  for (let k = 0; k < nc; k++) {
    const a = (k / nc) * Math.PI * 2 * 2.618 + (rnd() - 0.5) * 0.8, d = S * (0.02 + 0.3 * Math.sqrt((k + rnd()) / nc)) * o.spread;
    const len = S * o.size * (0.8 + 0.5 * rnd()), wid = len * (0.55 + 0.3 * rnd());
    const ax = a + (rnd() - 0.5) * 0.9;                      // pointing outwards, more or less
    sprays.push({ x: cx + Math.cos(a) * d, y: cy + Math.sin(a) * d * 0.9, len, wid, ax, hue: (rnd() - 0.5) * o.hue * 2 });
  }
  // autumn: a share of the sprays turned (blossom mask channel = 1; the species' bloomPal colours them)
  if (o.turn) for (const c of sprays) c.turned = rnd() < o.turn;
  for (const c of sprays) {                                  // twigs to each spray's base
    ctx.strokeStyle = rgb(0.08, 0, 0.5);
    ctx.lineWidth = 1 + rnd() * 0.8;
    ctx.beginPath();
    ctx.moveTo(cx + (rnd() - 0.5) * 8, cy + S * 0.08);
    ctx.lineTo(c.x - Math.cos(c.ax) * c.len * 0.3, c.y - Math.sin(c.ax) * c.len * 0.3);
    ctx.stroke();
  }
  const leaves = [];
  const per = Math.round(o.n / nc);
  for (const c of sprays) {
    const ca = Math.cos(c.ax), sa = Math.sin(c.ax);
    for (let i = 0; i < per; i++) {
      let u, v;
      do { u = rnd() * 2 - 1; v = rnd() * 2 - 1; } while (u * u + v * v > 1);
      const x = c.x + ca * u * c.len / 2 - sa * v * c.wid / 2, y = c.y + sa * u * c.len / 2 + ca * v * c.wid / 2;
      if (x < ox + 3 || x > ox + S - 3 || y < oy + 3 || y > oy + S - 3) continue;
      const out = Math.sqrt(u * u + v * v);
      const top = -(y - c.y) / (c.wid * 0.6);                  // upper side of the spray
      const gTop = -(y - cy) / (S * 0.4);                      // upper side of the cluster
      // lit from above: tops and tips bright, the spray's base and underside in shade
      const lum = 0.44 + 0.09 * top + 0.08 * (u * 0.5 + 0.5) + 0.1 * (out - 0.5) - 0.14 * (1 - out) ** 2
        + 0.08 * gTop + (rnd() - 0.5) * 0.36;
      const dir = c.ax + v * 0.9 + (rnd() - 0.5) * 1.1 + 0.2;  // leaves fan out along the spray, droop a little
      leaves.push({ x, y, dir, lum, hue: 0.5 + c.hue + (rnd() - 0.5) * o.hue, s: 0.7 + 0.6 * rnd(),
        g: c.turned && rnd() < 0.6 ? 1 : 0 });      // (turned sprays keep some green leaves)
    }
  }
  leaves.sort((p, q) => p.lum - q.lum);                      // the dark ones behind
  for (const l of leaves) {
    const L = o.L * l.s, W = o.W * l.s;
    ctx.save();
    ctx.translate(l.x, l.y);
    ctx.rotate(l.dir);
    const upper = Math.cos(l.dir) > 0 ? -1 : 1;             // which half faces the sky
    if (o.form) drawLeaf(ctx, o.form, L, W, l, upper);
    else {
      for (const sgn of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(-L * 0.5, 0);
        ctx.quadraticCurveTo(-L * 0.05, sgn * W, L * 0.5, 0);
        ctx.closePath();
        ctx.fillStyle = rgb(l.lum * (sgn === upper ? 1.12 : 0.86), l.g, l.hue);
        ctx.fill();
      }
    }
    ctx.restore();
  }
  if (o.flowers) {                                           // blossom: clusters of five-petal flowers on top
    for (let i = 0; i < o.flowers; i++) {
      const c = sprays[Math.floor(rnd() * nc)], a = -Math.PI * rnd(), rr = c.wid * (0.2 + 0.4 * rnd());
      const x = c.x + Math.cos(a) * rr, y = c.y + Math.sin(a) * rr, s = 2.2 + 1.6 * rnd(), lum = 0.5 + 0.45 * rnd();
      for (let p = 0; p < 5; p++) {
        const pa = (p / 5) * Math.PI * 2 + rnd();
        ctx.beginPath();
        ctx.ellipse(x + Math.cos(pa) * s, y + Math.sin(pa) * s, s, s * 0.6, pa, 0, Math.PI * 2);
        ctx.fillStyle = rgb(lum * (0.85 + 0.3 * rnd()), 1, 0.5);
        ctx.fill();
      }
    }
  }
}

// Leaf shapes other than the plain lens, drawn along +x from the leaf's middle (L long, W half-wide):
//   lobed     a palmately lobed blade (plane, maple): five pointed lobes, the sunny half lighter
//   palmate   a compound leaf of five to seven leaflets fanning from the stalk (horse chestnut)
//   needle    a tuft of needles (pines)
function drawLeaf(ctx, form, L, W, l, upper) {
  const lit = (k) => rgb(l.lum * k, l.g, l.hue);
  if (form === 'lobed') {
    const R = Math.max(L, W) * 0.5;
    ctx.beginPath();
    for (let k = 0; k <= 10; k++) {
      const a = (k / 10) * Math.PI * 2, r = k % 2 ? R * 0.5 : R * (k === 5 ? 0.6 : 1);
      const px = Math.cos(a) * r, py = Math.sin(a) * r * 0.95;
      if (k === 0) ctx.moveTo(px, py);
      else {
        const am = ((k - 0.5) / 10) * Math.PI * 2, rm = R * 0.78;
        ctx.quadraticCurveTo(Math.cos(am) * rm, Math.sin(am) * rm, px, py);
      }
    }
    ctx.closePath();
    ctx.fillStyle = lit(0.9);
    ctx.fill();
    ctx.beginPath();                                   // the half towards the sky lighter
    ctx.ellipse(0, upper * R * 0.25, R * 0.7, R * 0.45, 0, 0, Math.PI * 2);
    ctx.fillStyle = lit(1.1);
    ctx.fill();
  } else if (form === 'palmate') {
    for (let j = -3; j <= 3; j++) {
      const a = j * 0.42, len = L * (1 - Math.abs(j) * 0.14), w = W * (1 - Math.abs(j) * 0.1);
      ctx.save();
      ctx.rotate(a);
      for (const sgn of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.quadraticCurveTo(len * 0.55, sgn * w, len, 0);
        ctx.closePath();
        ctx.fillStyle = lit(sgn === upper ? 1.1 : 0.86);
        ctx.fill();
      }
      ctx.restore();
    }
  } else if (form === 'needle') {
    ctx.lineWidth = Math.max(1, W);
    for (let j = 0; j < 9; j++) {
      const a = (j / 8 - 0.5) * 1.6;
      ctx.strokeStyle = lit(j % 2 ? 1.08 : 0.88);
      ctx.beginPath();
      ctx.moveTo(-L * 0.3, 0);
      ctx.lineTo(-L * 0.3 + Math.cos(a) * L, Math.sin(a) * L * 0.8);
      ctx.stroke();
    }
  }
}

// a pinnate frond along x: the rachis in the middle, leaflets swept forward on both sides
function drawFrond(ctx, ox, oy, w, h, rnd) {
  const y0 = oy + h / 2;
  for (let t = 4; t < w - 4; t += 3.2) {
    const f = t / w, len = (h / 2 - 6) * Math.pow(Math.sin(Math.PI * Math.min(1, 0.07 + f * 0.97)), 0.55);
    for (const side of [-1, 1]) {
      if (rnd() < 0.07) continue;                          // a gap here and there
      const ang = side * (0.95 + (rnd() - 0.5) * 0.35), l = len * (0.85 + 0.3 * rnd());
      const x = ox + t, tx = x + Math.cos(ang) * l * 0.55, ty = y0 + Math.sin(ang) * l;
      const lum = 0.42 + 0.3 * rnd() + 0.1 * (1 - f);
      ctx.beginPath();
      ctx.moveTo(x - 2, y0);
      ctx.quadraticCurveTo(x + (tx - x) * 0.3 - 2, y0 + (ty - y0) * 0.6, tx, ty);
      ctx.quadraticCurveTo(x + (tx - x) * 0.3 + 2, y0 + (ty - y0) * 0.6, x + 2, y0);
      ctx.fillStyle = rgb(lum, 0, 0.5 + (rnd() - 0.5) * 0.15);
      ctx.fill();
    }
  }
  ctx.strokeStyle = rgb(0.62, 0, 0.35);                    // the rachis, pale
  for (let t = 0; t < w; t += 8) {
    ctx.lineWidth = 3.5 * (1 - t / w) + 0.8;
    ctx.beginPath();
    ctx.moveTo(ox + t, y0);
    ctx.lineTo(ox + t + 9, y0);
    ctx.stroke();
  }
}

// Mipmaps of RGBA8 data (premultiplied by alpha or not, see below) that keep alpha-tested coverage: after
// each 2x2 reduction the alpha of every cell (tile / frame) is scaled so that as many texels pass the
// test at `ref` as at full size, so thin foliage doesn't thin out with distance. RGB is averaged weighted
// by alpha; fully transparent texels take their cell's mean colour, so filtering doesn't bleed black.
function coverageMips(data, W, H, cw, ch, levels, ref = 0.5) {
  const cellsX = W / cw, cellsY = H / ch;
  const target = new Float64Array(cellsX * cellsY);
  // level 0: fill transparent texels and measure coverage
  for (let cyi = 0; cyi < cellsY; cyi++) {
    for (let cxi = 0; cxi < cellsX; cxi++) {
      let sr = 0, sg = 0, sb = 0, sa = 0, n = 0;
      for (let y = cyi * ch; y < (cyi + 1) * ch; y++) {
        for (let x = cxi * cw; x < (cxi + 1) * cw; x++) {
          const i = (y * W + x) * 4, a = data[i + 3];
          if (a > 0) { sr += data[i] * a; sg += data[i + 1] * a; sb += data[i + 2] * a; sa += a; }
          if (a >= ref * 255) n++;
        }
      }
      target[cyi * cellsX + cxi] = n / (cw * ch);
      const mr = sa ? sr / sa : 128, mg = sa ? sg / sa : 0, mb = sa ? sb / sa : 128;
      for (let y = cyi * ch; y < (cyi + 1) * ch; y++) {
        for (let x = cxi * cw; x < (cxi + 1) * cw; x++) {
          const i = (y * W + x) * 4;
          if (data[i + 3] === 0) { data[i] = mr; data[i + 1] = mg; data[i + 2] = mb; }
        }
      }
    }
  }
  const mips = [{ data, width: W, height: H }];
  let src = data, w = W, h = H;
  for (let l = 1; l <= levels; l++) {
    const nw = w >> 1, nh = h >> 1, dst = new Uint8Array(nw * nh * 4), af = new Float32Array(nw * nh);
    for (let y = 0; y < nh; y++) {
      for (let x = 0; x < nw; x++) {
        let r = 0, g = 0, b = 0, a = 0, pr = 0, pg = 0, pb = 0;
        for (const [dx, dy] of [[0, 0], [1, 0], [0, 1], [1, 1]]) {
          const i = ((2 * y + dy) * w + 2 * x + dx) * 4, aa = src[i + 3] + 1;
          r += src[i] * aa; g += src[i + 1] * aa; b += src[i + 2] * aa; a += aa;
          pr += src[i]; pg += src[i + 1]; pb += src[i + 2];
        }
        const o = (y * nw + x) * 4;
        dst[o] = r / a; dst[o + 1] = g / a; dst[o + 2] = b / a;
        af[y * nw + x] = (a - 4) / 4;
      }
    }
    // per cell: scale alpha so the share above ref matches level 0
    const lcw = cw >> l, lch = ch >> l;
    for (let cyi = 0; cyi < cellsY; cyi++) {
      for (let cxi = 0; cxi < cellsX; cxi++) {
        const vals = [];
        for (let y = cyi * lch; y < (cyi + 1) * lch; y++) for (let x = cxi * lcw; x < (cxi + 1) * lcw; x++) vals.push(af[y * nw + x]);
        vals.sort((p, q) => q - p);
        const k = Math.round(target[cyi * cellsX + cxi] * vals.length);
        const ak = k > 0 ? vals[Math.min(k, vals.length) - 1] : 0;
        const scale = ak > 1 ? Math.min(4, Math.max(1, (ref * 255 + 0.5) / ak)) : 1;
        for (let y = cyi * lch; y < (cyi + 1) * lch; y++) {
          for (let x = cxi * lcw; x < (cxi + 1) * lcw; x++) dst[(y * nw + x) * 4 + 3] = Math.min(255, af[y * nw + x] * scale);
        }
      }
    }
    mips.push({ data: dst, width: nw, height: nh });
    src = dst; w = nw; h = nh;
  }
  return mips;
}

function dataTexture(mips) {
  const t = new THREE.DataTexture(mips[0].data, mips[0].width, mips[0].height, THREE.RGBAFormat, THREE.UnsignedByteType);
  t.mipmaps = mips;
  t.generateMipmaps = false;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  t.magFilter = THREE.LinearFilter;
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  t.anisotropy = 4;
  t.colorSpace = THREE.NoColorSpace;
  t.needsUpdate = true;
  return t;
}

function leafAtlas() {
  const cv = document.createElement('canvas');
  cv.width = cv.height = ATLAS;
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  const rnd = rng(7);
  const done = new Set();                       // a tile several species share: drawn once, the first's leaves
  for (const [kind, tiles] of Object.entries(TILES)) {
    for (const t of tiles) {
      if (!done.has(t)) drawCluster(ctx, (t % 4) * TILE, Math.floor(t / 4) * TILE, LEAF[kind], rnd);
      done.add(t);
    }
  }
  if (SPECIES.some((s) => s.palm)) drawFrond(ctx, (FROND % 4) * TILE, Math.floor(FROND / 4) * TILE, 2 * TILE, TILE, rnd);
  const img = ctx.getImageData(0, 0, ATLAS, ATLAS);
  return dataTexture(coverageMips(new Uint8Array(img.data.buffer), ATLAS, ATLAS, TILE, TILE, 5));
}
// uv rectangle of an atlas tile; v grows downwards in the canvas (row 0 = v 0)
const tileUV = (t, span = 1) => [(t % 4) / 4, Math.floor(t / 4) / 4, span / 4, 1 / 4];

// ---------------------------------------------------------------- tree models
// Built in canonical metres, stored normalised: broadleaf positions as (x / R, y / h, z / R), palms as
// position / h. Attributes: position (anchor), offs (wood: radial offset in trunk radii; card: corner in
// crown radii, in the camera plane), normal, uv (leaf atlas), info (kind 0 wood / 1 leaves / 2 plain
// green, baked occlusion, random).
class Model {
  constructor() { this.a = { position: [], offs: [], normal: [], uv: [], info: [] }; this.idx = []; this.box = new THREE.Box3(); }
  v(p, o, n, u, v, kind, ao, r) {
    const a = this.a;
    a.position.push(p.x, p.y, p.z); a.offs.push(o.x, o.y, o.z); a.normal.push(n.x, n.y, n.z);
    a.uv.push(u, v); a.info.push(kind, ao, r);
    return a.position.length / 3 - 1;
  }
  quad(a, b, c, d) { this.idx.push(a, b, c, a, c, d); }
  geometry() {
    const g = new THREE.BufferGeometry();
    for (const [k, arr] of Object.entries(this.a)) g.setAttribute(k, new THREE.Float32BufferAttribute(arr, k === 'uv' ? 2 : 3));
    g.setIndex(this.idx);
    return g;
  }
}
// a vector perpendicular to t
const perp = (t) => (Math.abs(t.y) < 0.9 ? V3(0, 1, 0) : V3(1, 0, 0)).cross(t).normalize();

// a tapered tube along pts (metres) with radii (metres). norm maps a canonical point to stored units;
// rigid tubes (palms) bake the radius into the position, others store it as an offset in trunk radii
function tube(m, pts, radii, sides, { norm, rt = 0, ao = () => 1, kind = 0, shade = 0 }) {
  const rings = [];
  for (let i = 0; i < pts.length; i++) {
    const t = pts[Math.min(i + 1, pts.length - 1)].clone().sub(pts[Math.max(i - 1, 0)]).normalize();
    const a = perp(t), b = t.clone().cross(a);
    const ring = [];
    for (let s = 0; s <= sides; s++) {
      const ang = (s / sides) * Math.PI * 2, dir = a.clone().multiplyScalar(Math.cos(ang)).addScaledVector(b, Math.sin(ang));
      const n = dir.clone().addScaledVector(V3(0, 1, 0), shade).normalize();
      const p = rt ? norm(pts[i]) : norm(pts[i].clone().addScaledVector(dir, radii[i]));
      const o = rt ? dir.clone().multiplyScalar(radii[i] / rt) : V3();
      ring.push(m.v(p, o, n, s / sides, i / (pts.length - 1), kind, ao(pts[i], dir), 0.5));
      m.box.expandByPoint(pts[i].clone().addScaledVector(dir, radii[i]));
    }
    rings.push(ring);
  }
  for (let i = 1; i < rings.length; i++) {
    for (let s = 0; s < sides; s++) m.quad(rings[i - 1][s], rings[i - 1][s + 1], rings[i][s + 1], rings[i][s]);
  }
}
// a smooth curve through control points p0 -> p1 -> p2 (quadratic Bezier), n + 1 points
const curve = (p0, p1, p2, n) => Array.from({ length: n + 1 }, (_, i) => {
  const t = i / n;
  return p0.clone().multiplyScalar((1 - t) ** 2).addScaledVector(p1, 2 * t * (1 - t)).addScaledVector(p2, t * t);
});

// Broadleaf crowns: lobes (sub-crowns) inside an ellipsoidal envelope, each covered with leaf-cluster
// cards, a trunk forking into one limb per lobe. Parameters per species.
const BROAD = {
  banyan: { base: 0.3, lobes: 10, ring: 0.62, lobeR: [0.36, 0.46], cards: 8, size: [0.55, 0.75], fork: 0.3,
    flat: 0.8, inner: 1, roots: 4 },
  camphor: { base: 0.32, lobes: 8, ring: 0.52, lobeR: [0.4, 0.5], cards: 8, size: [0.55, 0.72], fork: 0.36,
    flat: 1, inner: 1 },
  acacia: { base: 0.45, lobes: 8, ring: 0.6, lobeR: [0.34, 0.44], cards: 8, size: [0.52, 0.72], fork: 0.45,
    flat: 0.75, inner: 0 },
  bloom: { base: 0.35, lobes: 8, ring: 0.56, lobeR: [0.36, 0.46], cards: 7, size: [0.55, 0.72], fork: 0.38,
    flat: 0.85, inner: 1 },
  mangrove: { base: 0.1, lobes: 7, ring: 0.6, lobeR: [0.4, 0.5], cards: 7, size: [0.52, 0.7], fork: 0.12,
    flat: 0.8, inner: 1, stems: true },
};
function broadleaf(sp, seed) {
  const S = SPECIES[sp], P = BROAD[S.name], rnd = rng(seed), m = new Model();
  const h = S.h, R = S.R, rt = (0.08 + 0.022 * h) * S.trunkK;
  const norm = (p) => V3(p.x / R, p.y / h, p.z / R);
  const yb = P.base * h, hc = (h - yb) / 2, cc = V3(0, yb + hc, 0);        // envelope: radii R, R, hc
  // lobes: one on top, the rest in a ring round the middle, some higher, some lower
  const lobes = [{ c: V3(0, cc.y + hc * 0.35, 0), r: Math.min(R, hc) * P.lobeR[1] * 1.1 }];
  // (`up`: the ring lobes' heights in the crown, [bias, spread]: up = (rnd - bias) * spread half-heights;
  // [0.4, 0.7] by default; a deep crown spreads them from its base to its top)
  const [upBias, upSpread] = P.up ?? [0.4, 0.7];
  for (let k = 1; k < P.lobes; k++) {
    const a = (k / (P.lobes - 1)) * Math.PI * 2 + (rnd() - 0.5) * 0.6;
    const ring = P.ring * (0.85 + 0.3 * rnd()), up = (rnd() - upBias) * upSpread;
    lobes.push({ c: V3(Math.cos(a) * R * ring, cc.y + hc * up * P.flat, Math.sin(a) * R * ring),
      r: R * (P.lobeR[0] + (P.lobeR[1] - P.lobeR[0]) * rnd()) });
  }
  // the limbs' paths (trunk to fork, fork to each lobe), and with `scaffold` [n, r, cards] n leaf clumps of r lobe radii
  // (and that many cards, else `cards`)
  // along each limb, so the leaves gather round the scaffold branches and hide the fork (London's planes: the
  // bare Y-arms under a thin disc read as acacias); none by default
  const fork = V3(0, P.fork * h, 0);
  const limbs = lobes.slice(1).map((L) => {
    const end = L.c.clone().multiplyScalar(0.8);
    const mid = fork.clone().lerp(end, 0.5).add(V3(0, (end.y - fork.y) * 0.25, 0));
    return { L, end, mid };
  });
  if (P.scaffold) {
    const [ns, rs] = P.scaffold;
    for (const { L, end, mid } of limbs) {
      for (let j = 0; j < ns; j++) {
        const t = 0.4 + (0.35 * (j + 0.5)) / ns + (rnd() - 0.5) * 0.1;
        const p = curve(fork, mid, end, 8)[Math.round(t * 8)];
        lobes.push({ c: p.clone().add(V3((rnd() - 0.5) * 0.6, 0.3, (rnd() - 0.5) * 0.6)), r: L.r * rs, scaffold: true });
      }
    }
  }
  const tiles = TILES[S.name];
  // cards
  for (const L of lobes) {
    const n = L.scaffold ? (P.scaffold[2] ?? P.cards) : P.cards + P.inner;
    for (let i = 0; i < n; i++) {
      const inner = !L.scaffold && i >= P.cards;
      // a direction on the lobe, fewer underneath (hidden and in shade anyway)
      let d;
      do d = V3(rnd() * 2 - 1, rnd() * 2 - 1, rnd() * 2 - 1); while (d.lengthSq() > 1 || d.lengthSq() < 0.05);
      d.normalize();
      if (d.y < -0.5 && rnd() < 0.6) d.y = -d.y * 0.5;
      d.normalize();
      const at = L.c.clone().addScaledVector(d, L.r * (inner ? 0.15 + 0.3 * rnd() : 0.55 + 0.45 * rnd()));
      at.y = Math.max(at.y, yb - 0.3);
      const eN = V3((at.x - cc.x) / R, (at.y - cc.y) / hc, (at.z - cc.z) / R);   // envelope coordinates
      const depth = eN.length();
      const nCrown = eN.clone().normalize();
      const n = d.clone().multiplyScalar(0.55).addScaledVector(nCrown, 0.45).add(V3(0, 0.12, 0)).normalize();
      // baked occlusion: deep inside and low in the crown darker; the underside of each lobe too
      let ao = (0.5 + 0.5 * smooth(clamp01((depth - 0.25) / 0.75))) * (0.75 + 0.25 * clamp01(0.5 + 0.7 * nCrown.y));
      ao *= 0.82 + 0.18 * (0.5 + 0.5 * d.y);
      if (inner) ao *= 0.6;
      const half = L.r * (P.size[0] + (P.size[1] - P.size[0]) * rnd()) * (inner ? 1.2 : 1) * CARD_UV * 2;
      const roll = (rnd() - 0.5) * 0.7, cr = Math.cos(roll), sr = Math.sin(roll);
      const tile = tiles[Math.floor(rnd() * tiles.length)], [u0, v0, du, dv] = tileUV(tile);
      const flip = rnd() < 0.5;                               // mirror some cards
      const r = rnd();
      const ids = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([x, y]) => {
        const ox = (x * cr - y * sr) * half / R, oy = (x * sr + y * cr) * half / R;
        // the card shows the inner part of its tile (the cluster; the corners are empty); card top = tile top
        const u = u0 + du * (0.5 + CARD_UV * (flip ? -x : x)), v = v0 + dv * (0.5 - CARD_UV * y);
        return m.v(norm(at), V3(ox, oy, 0), n, u, v, 1, ao, r);
      });
      m.quad(ids[0], ids[1], ids[2], ids[3]);
      m.box.expandByPoint(at.clone().add(V3(half * 1.3, half * 1.3, half * 1.3)));
      m.box.expandByPoint(at.clone().sub(V3(half * 1.3, half * 1.3, half * 1.3)));
    }
  }
  // wood: a trunk up to the fork, one limb out to each lobe (they show through the gaps)
  const woodAo = (p) => 0.6 + 0.4 * clamp01(1 - (p.y - yb) / (h - yb));
  const tubeOpts = { norm, rt, ao: (p) => (p.y > yb ? woodAo(p) * 0.7 : 1), shade: 0.2 };
  const stems = P.stems ? 3 : 1;
  for (let s = 0; s < stems; s++) {
    const a = rnd() * Math.PI * 2, off = P.stems ? V3(Math.cos(a) * 0.5, 0, Math.sin(a) * 0.5) : V3();
    tube(m, curve(off, off.clone().setY(fork.y * 0.5), fork, 3), [1.15, 1.0, 0.92, 0.85].map((x) => x * rt / stems ** 0.5), 7, tubeOpts);
  }
  // (a shape's `limbK`, opt-in: the limbs' thickness times this, 1 by default; Singapore's rain tree 0.6: one thick limb
  // reaching out from a low fork read as a second trunk leaning at 45 degrees)
  const lk = P.limbK ?? 1;
  for (const { end, mid } of limbs) tube(m, curve(fork, mid, end, 2), [0.55, 0.38, 0.16].map((x) => x * rt * lk), 5, tubeOpts);
  if (P.roots) {                                          // banyan aerial roots hanging from the limbs
    for (let i = 0; i < P.roots; i++) {
      const L = lobes[1 + Math.floor(rnd() * (lobes.length - 1))];
      const top = fork.clone().lerp(L.c.clone().multiplyScalar(0.8), 0.45 + 0.3 * rnd());
      tube(m, [top, top.clone().setY(top.y * 0.5), top.clone().setY(0)], [0.12, 0.14, 0.18].map((x) => x * rt), 4, tubeOpts);
    }
  }
  return m;
}

// Palms, rigid, stored as metres / h. Royal palm: straight grey column swelling a little below the middle,
// green crownshaft, 18 fronds arching out and down. Coconut: a curved, leaning trunk and 24 longer,
// drooping fronds whose leaflets hang.
function palm(sp, seed) {
  const S = SPECIES[sp], rnd = rng(seed), m = new Model(), h = S.h, royal = S.name === 'royal';
  const norm = (p) => p.clone().divideScalar(h);
  const topY = royal ? 0.79 * h : 0.94 * h;
  const lean = royal ? V3() : V3(1.8, 0, 0);
  const pts = curve(V3(), V3(0, topY * 0.5, 0).addScaledVector(lean, 0.15), V3(0, topY, 0).add(lean), 7);
  const radii = pts.map((p, i) => {
    const t = i / (pts.length - 1);
    return royal ? (0.3 - 0.1 * t + 0.04 * Math.sin(Math.PI * Math.min(1, t * 1.6))) + (i === 0 ? 0.05 : 0)
      : 0.24 - 0.07 * t + (i === 0 ? 0.06 : 0);
  });
  tube(m, pts, radii, 8, { norm, ao: (p) => 0.75 + 0.25 * clamp01(p.y / topY), shade: 0.1 });
  const top = pts.at(-1);
  let crown = top.clone();
  if (royal) {                                              // crownshaft
    const shaft = [top, top.clone().add(V3(0, 1.0, 0)), top.clone().add(V3(0, 2.0, 0))];
    tube(m, shaft, [0.21, 0.22, 0.17], 8, { norm, kind: 2, ao: () => 0.9, shade: 0.1 });
    crown = shaft[2].clone().add(V3(0, 0.1, 0));
  }
  const n = royal ? 18 : 24, [u0, v0, du, dv] = tileUV(FROND, 2);
  for (let f = 0; f < n; f++) {
    const az = f * 2.4 + (rnd() - 0.5) * 0.5;                   // golden-angle spiral
    const tier = f % 3;
    const rise = royal ? [0.95, 0.45, 0.02][tier] + (rnd() - 0.5) * 0.3 : [0.7, 0.2, -0.3][tier] + (rnd() - 0.5) * 0.3;
    const len = (royal ? 4.5 : 5.3) * (0.85 + 0.3 * rnd()) * (tier === 0 ? 0.85 : 1);
    const bend = royal ? 0.9 : 1.9, fold = royal ? 0.42 : 0.8, halfW = royal ? 1.05 : 0.95;
    const dir = V3(Math.cos(az), 0, Math.sin(az)), side = V3(-dir.z, 0, dir.x);
    const segs = 6, ring = [];
    let p = crown.clone().addScaledVector(dir, 0.15);
    for (let s = 0; s <= segs; s++) {
      const t = s / segs, ang = rise - bend * t * t - 0.3 * t;
      const tan = dir.clone().multiplyScalar(Math.cos(ang)).add(V3(0, Math.sin(ang), 0));
      if (s) p = p.clone().addScaledVector(tan, len / segs);
      const up = side.clone().cross(tan).normalize().negate();
      if (up.y < 0) up.negate();
      const w = halfW * Math.pow(Math.sin(Math.PI * Math.min(1, 0.06 + t * 0.97)), 0.55);
      // leaflets fold down from the rachis in a V
      const l = p.clone().addScaledVector(side, w * Math.cos(fold)).addScaledVector(up, -w * Math.sin(fold));
      const r = p.clone().addScaledVector(side, -w * Math.cos(fold)).addScaledVector(up, -w * Math.sin(fold));
      const radial = p.clone().sub(crown).normalize();
      const nrm = up.clone().multiplyScalar(0.45).addScaledVector(radial, 0.55).add(V3(0, 0.25, 0)).normalize();
      const ao = 0.7 + 0.3 * clamp01(t * 1.5);
      const u = u0 + du * t;
      ring.push([l, p, r].map((q, k) => {
        m.box.expandByPoint(q);
        return m.v(norm(q), V3(), nrm, u, v0 + dv * (k * 0.5), 1, ao * (k === 1 ? 0.9 : 1), f / n);
      }));
    }
    for (let s = 1; s <= segs; s++) {
      m.quad(ring[s - 1][0], ring[s][0], ring[s][1], ring[s - 1][1]);
      m.quad(ring[s - 1][1], ring[s][1], ring[s][2], ring[s - 1][2]);
    }
  }
  return m;
}

// ---------------------------------------------------------------- materials
// Shared uniforms, set every frame from the main camera and the sun (update()); the bake points them at
// its own camera. Cards face the camera; in the shadow pass they face the sun (castShadowPositionNode).
const U = {
  camPos: uniform(new THREE.Vector3()), camRight: uniform(new THREE.Vector3(1, 0, 0)), camUp: uniform(new THREE.Vector3(0, 1, 0)),
  sunDir: uniform(new THREE.Vector3(0, 1, 0)), sunRight: uniform(new THREE.Vector3(1, 0, 0)), sunUp: uniform(new THREE.Vector3(0, 0, 1)),
  sunColor: uniform(new THREE.Color(1, 1, 1)), bake: uniform(0), near: uniform(NEAR),
  skyK: uniform(1),                                // the sky light's strength, 1 by day, low at night
  // far rows (city.json trees.far {from, to, grow, bright}): impostors grow and brighten with distance so a
  // boulevard's row still reads from the overview (a crown of a few pixels loses its gaps and rim light);
  // 1, 1 by default: unchanged
  farFrom: uniform(1000), farTo: uniform(3000), farGrow: uniform(1), farBright: uniform(1),
};
const treeAttr = attribute('tree', 'vec4');        // x, z, height, crown width
const lookAttr = attribute('look', 'vec3');        // packed sRGB colour, species, ground height
// a per-tree random number from its position (kept positive and small enough for exact floats)
const seed = hash(treeAttr.x.mul(10).add(3e5).add(hash(treeAttr.y.mul(10).add(4e5)).mul(1e6)));
const seed2 = fract(seed.mul(71.3));
const turn = (v, a) => vec3(v.x.mul(cos(a)).sub(v.z.mul(sin(a))), v.y, v.x.mul(sin(a)).add(v.z.mul(cos(a))));
const unpack = (packed) => {                       // 24-bit sRGB -> linear
  const p = packed.add(0.5);
  const r = floor(p.div(65536)), g = floor(p.div(256)).sub(r.mul(256)), b = floor(p).sub(floor(p.div(256)).mul(256));
  return pow(vec3(r, g, b).div(255), vec3(2.2));
};
// The viewer's PBR Neutral tone mapping subtracts most of the smallest channel from dark colours (its toe),
// which turns shaded foliage into a saturated yellow-green with no blue at all. Photographed foliage in
// shade is greyer, so the leaf colour is desaturated towards its luminance before lighting.
const LEAF_SAT = 0.72;
const leafColor = varying((() => {
  const c = unpack(lookAttr.x);
  return mix(vec3(dot(c, vec3(0.2126, 0.7152, 0.0722))), c, LEAF_SAT);
})());
// screen-door dithering for level-of-detail fades (the same threshold everywhere, so near and impostor
// fragments of one tree are exact complements)
const dither = fract(float(52.9829189).mul(fract(dot(screenCoordinate.xy, vec2(0.06711056, 0.00583715)))));
// distance from the (main) camera to the middle of the tree, the same measure fill() sorts trees by
const treeDist = length(vec3(treeAttr.x, treeAttr.z.mul(0.5).add(lookAttr.z), treeAttr.y).sub(U.camPos));
const nearFade = varying(select(U.bake.greaterThan(0.5), float(0), smoothstep(U.near.sub(FADE), U.near, treeDist)));
// (a function: FAR and FAR_FADE are read when the impostor material is made, after city.json's trees.carpetBlend)
const farFadeNode = () => varying(smoothstep(FAR - FAR_FADE, FAR, treeDist));
// hue jitter from the atlas: yellower or bluer greens
const hueTint = (b) => mix(vec3(1.08, 1.02, 0.85), vec3(0.9, 1.0, 1.12), b);
const LMAX = 1.6;                                  // leaf brightness range, for the impostor encoding
const bloomColor = (s, pal = BLOOM) => {
  const c = [0, 1, 2, 3].map((i) => new THREE.Color(pal[i % pal.length]));
  const pick = floor(s.mul(4));
  return select(pick.lessThan(1), vec3(...c[0].toArray()), select(pick.lessThan(2), vec3(...c[1].toArray()),
    select(pick.lessThan(3), vec3(...c[2].toArray()), vec3(...c[3].toArray()))));
};
// leaves seen against the sun glow with transmitted light; the rest of the crown gets a little skylight
// (which fades after sunset, or the crowns would glow in the dark)
const translucency = (albedo, n) => {
  const view = normalize(positionWorld.sub(U.camPos));
  const back = pow(saturate(dot(view, U.sunDir)), 4);
  const thin = saturate(dot(n, U.sunDir).mul(-0.5).add(0.6));
  return albedo.mul(U.sunColor).mul(back.mul(thin).mul(0.55)).add(albedo.mul(U.skyK.mul(0.05)));
};

// Foliage is lit as diffuse only (Lambert): with spherical normals the standard material's specular term
// turned every crown top into a white sheen whenever the view faced a low sun (Fresnel goes to 1 at
// grazing angles), and a canopy's glints are far below what a crown-sized normal can show. It is also the
// cheaper shader, which matters with the overdraw of leaf cards.
const foliageMaterial = () => new THREE.MeshLambertNodeMaterial();

// near models: mode 'lit' for the scene, 'color' / 'normal' for the impostor bake
function nearMaterial(sp, atlas, mode) {
  const S = SPECIES[sp], lit = mode === 'lit';
  const m = lit ? foliageMaterial() : new THREE.MeshBasicNodeMaterial();
  const info = attribute('info', 'vec3'), offs = attribute('offs', 'vec3'), pos = attribute('position', 'vec3');
  const nrm = attribute('normal', 'vec3');
  const h = treeAttr.z, R = treeAttr.w.mul(0.5 * (S.wK ?? 1));
  const angle = seed.mul(6.2832);
  const base = vec3(treeAttr.x, lookAttr.z, treeAttr.y);
  const isLeaf = step(0.5, info.x).mul(step(info.x, 1.5));
  let place, normalW;
  if (S.palm) {
    place = () => turn(pos.mul(h), angle).add(base);
    normalW = turn(nrm, angle);
  } else {
    const rt = h.mul(0.022).add(0.08).mul(S.trunkK);
    const sx = R.div(S.R), sy = h.div(S.h);
    let anchor = vec3(pos.x.mul(R), pos.y.mul(h), pos.z.mul(R));
    // (city.json trees.trunkDrop, m, default 0: the trunk's foot ring reaches this far below the tree's base, so a
    // street tree lifted onto a sidewalk that isn't drawn under it (a plaza, a junction's corner) still meets the
    // ground; on the drawn surface the extra length is hidden under it. Berlin M6 critic: a trunk ending in mid-air)
    if (TRUNK_DROP) anchor = anchor.sub(vec3(0, step(pos.y, 1e-4).mul(isLeaf.oneMinus()).mul(TRUNK_DROP), 0));
    // per tree (a species' `lean` and `asym`, none by default): the trunk leans up to lean x its height (in its
    // own random direction, more towards the top), and the crown's lobes swell and shift by up to asym x R, a
    // smooth wobble seeded per tree, so a row of one model doesn't repeat (London's planes)
    if (S.lean) anchor = anchor.add(vec3(pow(pos.y, 1.5).mul(h).mul(S.lean).mul(seed2.mul(0.7).add(0.3)), 0, 0));
    if (S.asym) {
      const k = R.mul(S.asym).mul(pos.y);
      anchor = anchor.add(vec3(sin(pos.z.mul(2.7).add(seed.mul(41))).mul(k), sin(pos.x.mul(2.3).add(seed.mul(29))).mul(k).mul(0.5),
        sin(pos.x.mul(2.9).add(seed.mul(17))).mul(k)));
    }
    const wood = turn(anchor.add(offs.mul(rt).mul(isLeaf.oneMinus())), angle).add(base);
    place = (right, up) => wood.add(right.mul(offs.x).add(up.mul(offs.y)).mul(R).mul(isLeaf));
    // normals under the non-uniform scale, bent a little towards each card's corner so a card shades
    // as a rounded clump rather than a flat plate
    const nS = normalize(vec3(nrm.x.div(sx), nrm.y.div(sy), nrm.z.div(sx)));
    const bendV = U.camRight.mul(offs.x).add(U.camUp.mul(offs.y)).mul(isLeaf).mul(0.9);
    normalW = normalize(turn(nS, angle).add(bendV));
  }
  m.positionNode = S.palm ? place() : place(U.camRight, U.camUp);
  if (!S.palm) m.castShadowPositionNode = place(U.sunRight, U.sunUp);
  const vN = varying(normalW);
  const tex = texture(atlas, uv());
  const ao = info.y;
  // leaves: base colour x atlas brightness x hue jitter x occlusion, a card-to-card brightness wobble
  const L = tex.r.mul(1.12).add(0.26).mul(ao).mul(info.z.mul(0.3).add(0.85));
  // (a species' `turnVary`: per tree, up to that share of its turned leaves stay green, so an avenue of horse
  // chestnuts isn't one orange stripe; 0 by default)
  const turnK = (v) => float(1).sub(fract(seed.mul(53.1)).mul(v));
  const bloomAmt = S.bloom ? (S.turnVary && lit ? tex.g.mul(turnK(S.turnVary)) : tex.g) : float(0);
  // wood: bark with occlusion and some grain
  let woodL = ao.mul(mx_noise_float(positionWorld.mul(vec3(3, 0.6, 3))).mul(0.18).add(0.92));
  // (a species' `furrow` [depth, ridges per metre]: deep vertical furrows, dark between light ridges: the lime's and the
  // oak's bark, Berlin M4 fix round; none by default)
  if (S.furrow) {
    const [fk, ff] = S.furrow;
    woodL = woodL.mul(float(1).sub(smoothstep(-0.15, 0.35, mx_noise_float(positionWorld.mul(vec3(ff, ff / 30, ff)))).mul(fk)));
  }
  const shaftL = ao.mul(0.95);
  const kind = info.x;
  const alpha = select(isLeaf.greaterThan(0.5), tex.a, float(1));
  let bark = vec3(...new THREE.Color(S.bark).toArray());
  if (S.bark2) {                                   // mottled bark (plane trees shed it in patches)
    // (`mottle`: the noise band that turns to bark2, and the patch scale; Paris's planes shed more, smaller)
    const [m0, m1, ms] = S.mottle ?? [0.2, 0.32, 1];
    const patch = smoothstep(m0, m1, mx_noise_float(positionWorld.mul(vec3(3.2, 1.4, 3.2).mul(ms))));
    bark = mix(bark, vec3(...new THREE.Color(S.bark2).toArray()), patch);
  }
  if (lit) {
    const leafAlb = mix(leafColor.mul(hueTint(tex.b)), bloomColor(seed2, S.bloomPal).mul(1.1), bloomAmt).mul(L);
    const albedo = select(kind.lessThan(0.5), bark.mul(woodL), select(kind.lessThan(1.5), leafAlb, leafColor.mul(vec3(1.05, 1.15, 0.85)).mul(shaftL)));
    m.colorNode = vec4(albedo, alpha);
    m.normalNode = transformNormalToView(vN);
    m.emissiveNode = translucency(albedo, vN).mul(isLeaf);
    if (UPLIGHT) {
      const above = positionWorld.y.sub(lookAttr.z);
      const under = saturate(vN.y.mul(-0.5).add(0.7)).mul(exp(above.div(-(UPLIGHT.h ?? 8))));
      m.emissiveNode = m.emissiveNode.add(albedo.mul(vec3(...(UPLIGHT.colour ?? [1, 0.92, 0.8]))).mul(under).mul(UPLIGHT.lights).mul(UPLIGHT.k ?? 1).mul(isLeaf));
    }
    m.alphaTestNode = float(0.5);
    m.alphaToCoverage = true;
    // dissolve into the impostor with distance; shadows the same way (the sun pass keeps the mask)
    m.maskNode = nearFade.lessThan(dither);
    m.maskShadowNode = nearFade.lessThan(dither).and(alpha.greaterThan(0.5));
    // the crown's own cards facing the sun would shade most of it at shadow-map resolution (blotchy, and
    // unlike the impostor): look shadows up part of a crown radius sunwards, so buildings and other trees
    // still shade it and its lit and shaded sides come from the bent normals
    m.receivedShadowPositionNode = positionWorld.add(U.sunDir.mul(S.palm ? h.mul(0.12) : R.mul(SELF_SHADOW)));
  } else if (mode === 'color') {
    // impostor encoding: R brightness / LMAX (bark and crownshaft as their own brightness), G blossom,
    // B part (0 wood, 0.5 leaves, 1 crownshaft), A coverage
    const enc = select(kind.lessThan(0.5), woodL.div(LMAX), select(kind.lessThan(1.5), L.div(LMAX), shaftL.div(LMAX)));
    m.colorNode = vec4(enc, bloomAmt.mul(isLeaf), kind.mul(0.5), 1);
    m.alphaTest = 0.5;
    m.opacityNode = alpha;
  } else {
    // normal in the bake camera's frame (x right, y up, z towards the camera)
    const n = normalize(vN);
    m.colorNode = vec4(vec3(dot(n, U.camRight), dot(n, U.camUp), dot(n, cross(U.camRight, U.camUp))).mul(0.5).add(0.5), 1);
    m.alphaTest = 0.5;
    m.opacityNode = alpha;
  }
  m.side = THREE.DoubleSide;
  if (!lit) { m.fog = false; m.toneMapped = false; }
  return m;
}

// impostors: frames of COLS = species x azimuth variants, ROWS = elevations 0..90 degrees
const NE = 9, VARIANTS = 2, FRAME = 128, BAKE = 256;
let COLS = SPECIES.length * VARIANTS;         // (a city's species set changes it: useSpecies)
function impostorMaterial(tex, frames) {
  const m = foliageMaterial();
  const q = attribute('position', 'vec3');           // unit quad corner, -1..1
  const sp = lookAttr.y;
  // per-species canonical dimensions from a small table: [R, h, Hc, Wc, yc, D]
  const tbl = () => {
    let v = vec4(...frames[0].slice(0, 4)), w = vec2(...frames[0].slice(4, 6));
    for (let s = 1; s < frames.length; s++) {
      v = select(sp.greaterThan(s - 0.5), vec4(...frames[s].slice(0, 4)), v);
      w = select(sp.greaterThan(s - 0.5), vec2(...frames[s].slice(4, 6)), w);
    }
    return [v, w];
  };
  const [dimA, dimB] = tbl();
  const Rc = dimA.x, hc = dimA.y, Hc = dimA.z, Wc = dimA.w, yc = dimB.x, D = dimB.y;
  const wK = SPECIES.map((s) => s.wK ?? 1);
  let wKn = float(wK[0]);
  for (let s = 1; s < wK.length; s++) wKn = select(sp.greaterThan(s - 0.5), float(wK[s]), wKn);
  // per-species constants as select chains over the species id
  const perSp = (vals, one = float) => {
    let v = one(vals[0]);
    for (let s = 1; s < vals.length; s++) v = select(sp.greaterThan(s - 0.5), one(vals[s]), v);
    return v;
  };
  const palmK = perSp(SPECIES.map((s) => (s.palm ? 1 : 0)));
  // (trees.carpetBlend.shrink, opt-in: impostors also shrink towards the ground by up to this share as they dissolve
  // into the carpet, so a ridge against the sky loses its crowns smoothly instead of as a stipple of dithered ones)
  const shrinkK = BLEND?.shrink ? float(1).sub(smoothstep(FAR - FAR_FADE, FAR, treeDist).mul(BLEND.shrink)) : null;
  const h = shrinkK ? treeAttr.z.mul(shrinkK) : treeAttr.z, sv = h.div(hc);
  // (branchless: as a select this went into the shadow lookup's offset below with one operand left
  // uninitialised on some drivers, and impostors in a tower's shadow stayed lit on WebGPU, and on WebGL 2 on
  // some machines; the card's own size, built earlier in the vertex stage, was right)
  const farK = smoothstep(U.farFrom, U.farTo, treeDist);
  const sh = mix(treeAttr.w.mul(0.5).mul(wKn).div(Rc).mul(shrinkK ?? 1), sv, palmK).mul(farK.mul(U.farGrow.sub(1)).add(1));
  const C = vec3(treeAttr.x, yc.mul(sv).add(lookAttr.z), treeAttr.y);
  const variant = step(0.5, seed2), mirror = step(0.5, fract(seed2.mul(13.7)));
  const col = sp.mul(VARIANTS).add(variant);
  // a quad facing `toCam`, showing the frame nearest its elevation (blending two frames blurred the crown
  // and fattened its outline; frames 11 degrees apart hardly change when one gives way to the next)
  const frameOf = (toCam, fallbackRight) => {
    const e = asin(clamp(toCam.y, 0, 1));
    const k = floor(e.div(Math.PI / 2).mul(NE - 1).add(0.5));
    const rr = cross(vec3(0, 1, 0), toCam);
    const right = normalize(mix(fallbackRight, rr, smoothstep(0.0, 0.02, length(rr))));
    const up = cross(toCam, right);
    const ce = cos(e), se = sin(e);
    const sUp = sv.mul(Hc).mul(ce).add(sh.mul(Wc).mul(se)).div(Hc.mul(ce).add(Wc.mul(se)));
    const p = C.add(right.mul(q.x.mul(D).mul(0.5).mul(sh))).add(up.mul(q.y.mul(D).mul(0.5).mul(sUp)));
    const fu = mix(q.x, q.x.negate(), mirror).mul(0.5).add(0.5), fv = q.y.mul(0.5).add(0.5);
    const inset = 0.5 / FRAME;                        // keep bilinear taps inside the frame
    const cu = col.add(clamp(fu, inset, 1 - inset)).div(COLS);
    return { p, uv: vec2(cu, k.add(clamp(fv, inset, 1 - inset)).div(NE)), right, up };
  };
  const toCam = normalize(U.camPos.sub(C));
  const F = frameOf(toCam, U.camRight);
  m.positionNode = F.p;
  const S = frameOf(U.sunDir, U.sunRight);
  m.castShadowPositionNode = S.p;
  const fuv = varying(F.uv);
  const c = texture(tex.color, fuv), nn = texture(tex.normal, fuv);
  const vRight = varying(F.right.mul(mirror.mul(-2).add(1))), vUp = varying(F.up), vTo = varying(toCam);
  const nx = nn.x.mul(2).sub(1), ny = nn.y.mul(2).sub(1), nz = nn.z.mul(2).sub(1);
  const nW = normalize(vRight.mul(nx).add(vUp.mul(ny)).add(vTo.mul(nz)));
  const L = c.r.mul(LMAX), kind = c.b.mul(2);         // 0 wood, 1 leaves, 2 crownshaft
  const woodK = smoothstep(0.5, 0.2, kind), shaftK = smoothstep(1.4, 1.8, kind);
  const barks = SPECIES.map((s) => new THREE.Color(s.bark));
  let bark = vec3(...barks[0].toArray());
  for (let s = 1; s < barks.length; s++) bark = select(sp.greaterThan(s - 0.5), vec3(...barks[s].toArray()), bark);
  // blossom, or turned leaves (the species' bloom colours): only on species that have it
  const blooms = SPECIES.map((s) => (s.bloom ? 1 : 0));
  const varies = SPECIES.map((s) => (s.bloom ? 1 - (s.turnVary ?? 0) : 1));
  const turnAmt = varies.some((v) => v < 1) ? float(1).sub(fract(seed.mul(53.1)).mul(float(1).sub(perSp(varies)))) : float(1);
  const bloomAmt = blooms.some((b) => b) ? c.g.mul(perSp(blooms)).mul(turnAmt) : float(0);
  const bloomCol = blooms.some((b) => b) ? perSp(SPECIES.map((s) => s.bloomPal ?? BLOOM), (pal) => bloomColor(seed2, pal)) : vec3(0);
  const leafAlb = mix(leafColor, bloomCol.mul(1.1), bloomAmt);
  const shaft = leafColor.mul(vec3(1.05, 1.15, 0.85));
  const albedo = mix(mix(leafAlb, shaft, shaftK), bark, woodK).mul(L);
  m.colorNode = vec4(albedo.mul(varying(farK.mul(U.farBright.sub(1)).add(1))), c.a);
  m.normalNode = transformNormalToView(nW);
  m.emissiveNode = translucency(albedo, nW).mul(woodK.oneMinus());
  m.alphaTestNode = float(0.5);
  m.alphaToCoverage = true;
  m.maskNode = nearFade.greaterThanEqual(dither).and(farFadeNode().lessThan(dither.oneMinus()));
  // the sun's view of the tree, its own coverage test
  m.maskShadowNode = texture(tex.color, varying(S.uv)).a.greaterThan(0.5).and(nearFade.greaterThanEqual(dither));
  // the flat quad would shade itself with its own sun-facing twin: look shadows up sunwards, as near trees do
  m.receivedShadowPositionNode = positionWorld.add(U.sunDir.mul(sh.mul(Rc).mul(SELF_SHADOW)));
  m.side = THREE.DoubleSide;
  return m;
}

// Render every species from NE elevations and two azimuths (near model, one instance at the origin), one
// elevation at a time into a row of BAKE-pixel frames, twice (encoded colour, then normals); read each
// back, reduce to FRAME pixels and build coverage-keeping mipmaps.
async function bakeImpostors(renderer, geoms, atlas) {
  const W = COLS * BAKE;
  const rt = new THREE.RenderTarget(W, BAKE, { samples: 4, type: THREE.UnsignedByteType, depthBuffer: true });
  const scene = new THREE.Scene();
  const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 1, 1000);
  const frames = [];                                   // per species [R, h, Hc, Wc, yc, D]
  const meshes = SPECIES.map((S, sp) => {
    const g = new THREE.InstancedBufferGeometry();
    for (const k of Object.keys(geoms[sp].attributes)) g.setAttribute(k, geoms[sp].attributes[k]);
    g.setIndex(geoms[sp].index);
    g.setAttribute('tree', new THREE.InstancedBufferAttribute(new Float32Array([0, 0, S.h, S.palm ? S.h : 2 * S.R / (S.wK ?? 1)]), 4));
    g.setAttribute('look', new THREE.InstancedBufferAttribute(new Float32Array([0xffffff, sp, 0]), 3));
    g.instanceCount = 1;
    const mesh = new THREE.Mesh(g);
    mesh.userData.mats = [nearMaterial(sp, atlas, 'color'), nearMaterial(sp, atlas, 'normal')];
    mesh.frustumCulled = false;
    scene.add(mesh);
    const box = geoms[sp].userData.box;
    const Wc = 2 * Math.max(-box.min.x, box.max.x, -box.min.z, box.max.z), Hc = box.max.y - Math.min(0, box.min.y);
    const yc = (box.max.y + Math.min(0, box.min.y)) / 2, D = 1.03 * Math.hypot(Hc, Wc);
    frames.push([S.R, S.h, Hc, Wc, yc, D]);
    return mesh;
  });
  // the tree instance is at the origin: its hash-based rotation is the same in every frame, azimuth
  // variants come from moving the camera round it
  const prev = { target: renderer.getRenderTarget(), autoClear: renderer.autoClear, clear: renderer.getClearColor(new THREE.Color()),
    alpha: renderer.getClearAlpha() };
  const rows = [[], []];                               // [pass][k]: read-back pixels
  U.bake.value = 1;
  renderer.setClearColor(0x000000, 0);
  renderer.autoClear = false;
  for (let k = 0; k < NE; k++) {
    for (let pass = 0; pass < 2; pass++) {
      renderer.setRenderTarget(rt);
      renderer.clear();
      for (let sp = 0; sp < SPECIES.length; sp++) {
        const [, , , , yc, D] = frames[sp];
        meshes.forEach((m, j) => { m.visible = j === sp; m.material = m.userData.mats[pass]; });
        for (let v = 0; v < VARIANTS; v++) {
          const e = (k / (NE - 1)) * Math.PI / 2, az = v * Math.PI / 2;
          const dir = V3(Math.sin(az) * Math.cos(e), Math.sin(e), Math.cos(az) * Math.cos(e));
          cam.left = cam.bottom = -D / 2;
          cam.right = cam.top = D / 2;
          cam.position.set(0, yc, 0).addScaledVector(dir, 300);
          cam.up.set(-Math.sin(az) * Math.sin(e), Math.cos(e), -Math.cos(az) * Math.sin(e));
          cam.lookAt(0, yc, 0);
          cam.updateProjectionMatrix();
          cam.updateMatrixWorld();
          U.camPos.value.copy(cam.position);
          U.camRight.value.setFromMatrixColumn(cam.matrixWorld, 0);
          U.camUp.value.setFromMatrixColumn(cam.matrixWorld, 1);
          rt.viewport.set((sp * VARIANTS + v) * BAKE, 0, BAKE, BAKE);
          renderer.render(scene, cam);
        }
      }
      const px = await renderer.readRenderTargetPixelsAsync(rt, 0, 0, W, BAKE);
      rows[pass].push(new Uint8Array(px.buffer, px.byteOffset, px.byteLength));
    }
  }
  U.bake.value = 0;
  renderer.setRenderTarget(prev.target);
  renderer.autoClear = prev.autoClear;
  renderer.setClearColor(prev.clear, prev.alpha);
  rt.dispose();
  for (const mesh of meshes) { mesh.geometry.dispose(); for (const mm of mesh.userData.mats) mm.dispose(); }

  // Backends differ in which way up a read-back image comes (WebGL bottom row first, WebGPU top row
  // first). Find out from the first frame (a banyan from the side): its trunk (wood in the colour pass)
  // belongs at the bottom.
  let sum = 0, cnt = 0;
  for (let y = 0; y < BAKE; y++) {
    for (let x = 0; x < BAKE; x++) {
      const i = (y * W + x) * 4;
      if (rows[0][0][i + 3] > 200 && rows[0][0][i + 2] < 60) { sum += y; cnt++; }
    }
  }
  const bottomFirst = cnt > 0 && sum / cnt < BAKE / 2;
  // reduce to FRAME px per frame, un-premultiply (the clear was 0), and store with row 0 = frame bottom
  // (v = 0), frames stacked by elevation k from v = 0 upwards
  const FW = COLS * FRAME, FH = NE * FRAME, s = BAKE / FRAME;
  const col = new Uint8Array(FW * FH * 4), nor = new Uint8Array(FW * FH * 4);
  for (let k = 0; k < NE; k++) {
    const colorPx = rows[0][k], normalPx = rows[1][k];
    for (let fy = 0; fy < FRAME; fy++) {
      for (let fx = 0; fx < FW; fx++) {
        let cr = 0, cg = 0, cb = 0, ca = 0, nr = 0, ng = 0, nb = 0, na = 0;
        for (let dy = 0; dy < s; dy++) {
          const up = fy * s + dy, row = bottomFirst ? up : BAKE - 1 - up;
          for (let dx = 0; dx < s; dx++) {
            const i = (row * W + fx * s + dx) * 4;
            cr += colorPx[i]; cg += colorPx[i + 1]; cb += colorPx[i + 2]; ca += colorPx[i + 3];
            nr += normalPx[i]; ng += normalPx[i + 1]; nb += normalPx[i + 2]; na += normalPx[i + 3];
          }
        }
        const o = ((k * FRAME + fy) * FW + fx) * 4;
        col[o] = ca ? (255 * cr) / ca : 0; col[o + 1] = ca ? (255 * cg) / ca : 0; col[o + 2] = ca ? (255 * cb) / ca : 128;
        col[o + 3] = ca / (s * s);
        nor[o] = na ? (255 * nr) / na : 128; nor[o + 1] = na ? (255 * ng) / na : 128; nor[o + 2] = na ? (255 * nb) / na : 128;
        nor[o + 3] = col[o + 3];
      }
    }
  }
  const color = dataTexture(coverageMips(col, FW, FH, FRAME, FRAME, 4));
  const normal = dataTexture(coverageMips(nor, FW, FH, FRAME, FRAME, 4));
  return { tex: { color, normal }, frames, bottomFirst };
}

// ---------------------------------------------------------------- tile decoding
async function gunzip(buf) {
  const b = new Uint8Array(buf);
  if (b[0] !== 0x1f || b[1] !== 0x8b) return buf;     // a server may already have decoded it
  return new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
}
const unsplit16 = (u8, off, n) => {                    // low bytes then high bytes -> Int16Array
  const out = new Int16Array(n);
  for (let i = 0; i < n; i++) out[i] = (u8[off + n + i] << 8) | u8[off + i];
  return out;
};

// one tile's trees as arrays: x, z (scene), h, w, colour, rank (0: never thinned), species, and y, the ground
// under each (ground(x, z): the terrain's height, see terrain.js), less SINK
// streetLift (city.json trees.streetLift, m; default 0): street trees stand that much higher, on the sidewalks' and
// medians' drawn surface (06b_markings lays it ROAD_Y + OVER_Y, 1.4-1.6 m, over the ground): their trunks had passed
// through a median's top and showed again as a stub on the lower paving beside it (Berlin's Unter den Linden)
// (trees.json liftBit, 08_trees [trees] lift_flag: only trees with that bit of their kind byte set stand on the street
// surface and take streetLift; the census's park trees stand on the ground)
function tileTrees(buf, t, classes, cell, ground, table, streetSpecies = null, bits = 2, hq = 10, caps = false, streetLift = 0, liftBit = 0) {
  const u8 = new Uint8Array(buf), dv = new DataView(buf);
  const n = dv.getUint32(0, true), hasMask = dv.getUint32(4, true);
  const M = Math.round(1000 / cell);
  const mask = hasMask ? u8.subarray(8, 8 + M * M) : null;
  let off = 8 + (hasMask ? M * M : 0);
  const trees = { x: [], z: [], h: [], w: [], col: [], rank: [], sp: [], y: [] };
  const add = (x, z, h, w, col, rank, sp, lift = 0) => {
    trees.x.push(x); trees.z.push(z); trees.h.push(h); trees.w.push(w);
    trees.col.push(col); trees.rank.push(rank); trees.sp.push(sp); trees.y.push(ground(x, z) - SINK + lift);
  };
  // street trees: one species per road (the colour seed cs is per road), banyans and camphors, royal
  // palms (a few coconut palms), flowering trees
  const dx = unsplit16(u8, off, n), dz = unsplit16(u8, off + 2 * n, n);
  off += 4 * n;
  let qx = 0, qz = 0;
  for (let i = 0; i < n; i++) {
    qx += dx[i]; qz += dz[i];
    const k8 = u8[off + n + i], kind = liftBit ? k8 & ((1 << liftBit) - 1) : k8;
    const h = u8[off + i] / hq, species = kind & ((1 << bits) - 1), cs = kind >> bits;
    const lift = liftBit ? ((k8 >> liftBit) & 1) * streetLift : streetLift;
    const u = hash2(qx, qz, 11);
    // a census (trees.json streetSpecies) names the species slot of each group; otherwise Shenzhen's
    const sp = (streetSpecies ? SP[streetSpecies[species]] ?? SP.camphor
      : species === 1 ? (cs % 7 === 0 ? SP.coconut : SP.royal) : species === 2 ? SP.bloom
      : cs % 5 < 3 ? SP.banyan : SP.camphor) ?? 0;
    let w = SPECIES[sp].palm ? h : h * (0.75 + 0.3 * hash2(qx, qz, 12));
    // (trees.json caps: the crown radius kept off the nearest wall, 08_trees [trees] clip_walls)
    if (caps && !SPECIES[sp].palm) w = Math.min(w, (2 * u8[off + 2 * n + i] * 0.2) / (SPECIES[sp].wK ?? 1));
    // (a species' `vary`: the share of its street trees taking their own shade, not their road's; 0 by default)
    const vary = SPECIES[sp].vary ?? 0;
    const pu = vary && hash2(qx, qz, 13) < vary ? hash2(qx, qz, 14) : (cs % 16) / 16;
    add(t.x + qx / 10, t.z + qz / 10, h, w, treeColor(sp, pu, (vary ? 0.9 : 0.92) + (vary ? 0.2 : 0.16) * u), 0, sp, lift);
  }
  if (!mask) return pack(trees);
  // area trees: a jittered grid per class present, anchored to the scene so tiles meet seamlessly
  const present = new Set(mask);
  for (const id of present) {
    const name = classes[id], c = table[name];
    if (!c) continue;
    const s = c.step;
    for (let gi = Math.ceil(t.x / s); gi * s < t.x + 1000; gi++) {
      for (let gj = Math.ceil(t.z / s); gj * s < t.z + 1000; gj++) {
        const r1 = hash2(gi, gj, id), r2 = hash2(gi, gj, id + 50), r3 = hash2(gi, gj, id + 100);
        const x = (gi + 0.1 + 0.8 * r1) * s, z = (gj + 0.1 + 0.8 * r2) * s;
        const col = Math.floor((x - t.x) / cell), row = Math.floor((z - t.z) / cell);
        if (col < 0 || row < 0 || col >= M || row >= M || mask[row * M + col] !== id) continue;
        const grove = vnoise2(x / 70, z / 70, 3);
        const p = c.p * (1 - c.clump + c.clump * 2 * grove * grove * 1.4);
        if (r3 >= p) continue;
        // no trees on rock faces (steeper than ~41 degrees: the Palisades' upper face): the talus and the top keep theirs
        const gx0 = ground(x - 3, z), gx1 = ground(x + 3, z), gz0 = ground(x, z - 3), gz1 = ground(x, z + 3);
        if (Math.hypot(gx1 - gx0, gz1 - gz0) > 5.2) continue;
        const r4 = hash2(gi, gj, id + 150), r5 = hash2(gi, gj, id + 200), r6 = hash2(gi, gj, id + 250);
        // species: two trees in three take their grove's species (one uniform draw per ~40 m cell, the
        // cells' edges wobbled by noise), the rest their own; both draws are uniform, so the class's
        // species weights hold overall
        const gx = Math.floor((x + 25 * vnoise2(x / 60, z / 60, 21)) / 40), gz = Math.floor((z + 25 * vnoise2(x / 60, z / 60, 22)) / 40);
        // (a class's `grove`, opt-in: that share instead of two in three; Singapore's parks 0.92, so a flowering tree
        // stands with others of its kind, a patch of yellow, not one in every few crowns)
        const pick = hash2(gi, gj, id + 400) < (c.grove ?? 0.65) ? hash2(gx, gz, id + 450) : r5;
        const sp = (c.cum.find(([, acc]) => pick < acc) ?? c.cum.at(-1))[0];
        const isPalm = SPECIES[sp].palm;
        const h = isPalm ? 10 + 6 * r4 : c.h[0] + (c.h[1] - c.h[0]) * (0.25 * r4 + 0.75 * vnoise2(x / 40, z / 40, 9));
        const w = isPalm ? h : h * (c.wr[0] + (c.wr[1] - c.wr[0]) * r6);
        const color = treeColor(sp, hash2(gi, gj, id + 300), c.tone * (0.88 + 0.24 * r4));
        add(x, z, h, w, color, c.thin ? Math.max(1e-6, hash2(gi, gj, id + 350)) : 0, sp);
      }
    }
  }
  return pack(trees);
}
function pack(t) {
  const n = t.x.length;
  return {
    n, x: Float32Array.from(t.x), z: Float32Array.from(t.z), h: Float32Array.from(t.h), w: Float32Array.from(t.w),
    col: Float32Array.from(t.col), rank: Float32Array.from(t.rank), sp: Uint8Array.from(t.sp), y: Float32Array.from(t.y),
    y0: t.y.reduce((a, b) => Math.min(a, b), Infinity), y1: t.y.reduce((a, b) => Math.max(a, b), -Infinity),
  };
}

// ---------------------------------------------------------------- the module
// classes: city.json's trees.classes (see CLASS)
// A city's own species (city.json trees.species): each entry re-dresses one of the slots above, keeping its
// place in the table (palms stay last): h, R, wK, trunkK, bark (bark2: mottled with this), pal, bloom (bloomPal:
// its colours, also turned autumn leaves), and `shape` (BROAD's crown parameters) and `leaf` (LEAF's cluster
// drawing) merged over the slot's. New York's plane trees, honey locusts, pears and lindens stand in the banyan,
// acacia, bloom and camphor slots. An entry with a new name and `like` (an existing slot) adds a species built
// like it, on the atlas tiles `tiles` (its own, or the like's); `drop: true` removes a slot the city has no use
// for (Paris: palms, mangroves), so it is neither baked nor drawn.
function useSpecies(own = {}) {
  const drop = new Set(Object.entries(own).filter(([, o]) => o.drop).map(([n]) => n));
  for (const [name, o] of Object.entries(own)) {
    if (o.drop) continue;
    let S = SPECIES[SP[name]];
    if (!S) {
      const like = SPECIES[SP[o.like]];
      if (!like) throw new Error(`trees.species: no slot "${name}" (a new species needs like: an existing slot)`);
      S = { ...like, name };
      SPECIES.push(S);
      SP[name] = SPECIES.length - 1;
      if (BROAD[o.like]) BROAD[name] = { ...BROAD[o.like] };
      if (LEAF[o.like]) LEAF[name] = { ...LEAF[o.like] };
      if (TILES[o.like]) TILES[name] = TILES[o.like];
    }
    const { shape, leaf, like, tiles, ...rest } = o;
    Object.assign(S, rest);
    if (shape) BROAD[name] = { ...BROAD[name], ...shape };
    if (leaf) LEAF[name] = { ...LEAF[name], ...leaf };
    if (tiles) TILES[name] = tiles;
  }
  const kept = SPECIES.filter((S) => !drop.has(S.name)).sort((a, b) => (a.palm ? 1 : 0) - (b.palm ? 1 : 0));
  SPECIES.length = 0;
  SPECIES.push(...kept);
  SP = Object.fromEntries(SPECIES.map((S, i) => [S.name, i]));
  for (const n of Object.keys(TILES)) if (!(n in SP)) delete TILES[n];
  COLS = SPECIES.length * VARIANTS;
  PALC = SPECIES.map((S) => S.pal.map(sRGB));
}

export async function createTrees({ scene, camera, invalidate, renderer, terrain, url = 'trees/', classes = {}, species = {}, dense = null, far = null, streetLift = 0, trunkDrop = 0, carpetBranch = false, carpetNormals = false, carpetBlend = null, uplight = null }) {
  UPLIGHT = uplight;
  useSpecies(species);
  // (city.json trees.carpetBlend, opt-in, Hong Kong M7f: { reach, fade, colours, glow, tint }: where the trees end
  // (FAR, reach m from the camera) the forest dissolves into the carpet over `fade` m (600 by default), the carpet's
  // class colours (`colours`, sRGB by class) and `tint` (a multiplier) matched to the impostor canopy's mean, and a
  // backlit glow on the carpet as the impostors' leaves have (`glow`, their 0.55 share): a hillside half in
  // instanced crowns (lit, glowing against the sun) and half in a dark smooth carpet read as wooded below a line and
  // bare above it (the user, 6 Oct; critic M7). Absent: off, FAR 4500 / 600 and the carpet as before)
  if (carpetBlend) {
    BLEND = carpetBlend;
    FAR = carpetBlend.reach ?? FAR;
    FAR_FADE = carpetBlend.fade ?? FAR_FADE;
  }
  TRUNK_DROP = trunkDrop;
  CARPET_BRANCH = carpetBranch;
  CARPET_NORMALS = carpetNormals;
  if (far) {
    U.farFrom.value = far.from ?? 1000; U.farTo.value = far.to ?? 3000;
    U.farGrow.value = far.grow ?? 1; U.farBright.value = far.bright ?? 1;
  }
  if (dense) DENSE = new Set(dense);
  const index = await fetch(url + 'trees.json', { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  const group = new THREE.Group();
  group.name = 'trees';
  scene.add(group);
  // no trees folder: an empty group, the viewer runs without them
  if (!index) return { group, update() {}, stats: {}, meshes: [], index, setNear() {}, loadCarpet() {} };
  const table = classTable(classes);
  const blend = {};

  // carpet: loaded once the view is up (main.js calls loadCarpet), it is only seen from afar
  async function loadCarpet() {
    const buf = await gunzip(await (await fetch(url + index.carpet)).arrayBuffer());
    const dv = new DataView(buf), u8 = new Uint8Array(buf);
    const nv = dv.getUint32(0, true), ni = dv.getUint32(4, true);
    const dx = unsplit16(u8, 8, nv), dz = unsplit16(u8, 8 + 2 * nv, nv);
    // the ground's height under each vertex (08_trees.py laid the carpet on the terrain), unsigned
    const dy = new Uint16Array(unsplit16(u8, 8 + 4 * nv, nv).buffer);
    const cls = u8.subarray(8 + 6 * nv, 8 + 7 * nv);
    const pos = new Float32Array(nv * 3), normal = new Float32Array(nv * 3), color = new Float32Array(nv * 3), dense = new Float32Array(nv);
    const own = BLEND?.colours ?? {};
    const q = index.carpetQuant, yq = index.carpetYQuant ?? 0, palette = index.classes.map((c) => new THREE.Color(own[c] ?? CARPET[c] ?? '#000000'));
    // (trees.carpetBlend: the carpet's own colours nearer than the dissolve band, the floor under the stands; see below)
    const palette0 = index.classes.map((c) => new THREE.Color(CARPET[c] ?? own[c] ?? '#000000'));
    const color0 = BLEND ? new Float32Array(nv * 3) : null;
    const isDense = index.classes.map((c) => (DENSE.has(c) ? 1 : 0));
    let x = 0, z = 0;
    for (let i = 0, o = 0; i < nv; i++, o += 3) {
      x += dx[i]; z += dz[i];
      pos[o] = x * q; pos[o + 1] = dy[i] * yq + CARPET_Y; pos[o + 2] = z * q;
      normal[o + 1] = 1;
      const c = palette[cls[i]];
      color[o] = c.r; color[o + 1] = c.g; color[o + 2] = c.b;
      if (color0) { const c0 = palette0[cls[i]]; color0[o] = c0.r; color0[o + 1] = c0.g; color0[o + 2] = c0.b; }
      dense[i] = isDense[cls[i]];
    }
    const ioff = 8 + 7 * nv + ((4 - ((8 + 7 * nv) % 4)) % 4);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('normal', new THREE.BufferAttribute(normal, 3));
    g.setAttribute('color', new THREE.BufferAttribute(color, 3));
    g.setAttribute('dense', new THREE.BufferAttribute(dense, 1));
    if (color0) g.setAttribute('color0', new THREE.BufferAttribute(color0, 3));
    g.setIndex(new THREE.BufferAttribute(new Uint32Array(buf.slice(ioff, ioff + 4 * ni)), 1));
    // (city.json trees.carpetNormals, opt-in: the carpet shaded with its own slope, the ground's under it, not as level
    // ground: on a hillside facing away from the sun the level normal lit the far canopy as if in full sun wherever the
    // shadow map missed it, so the slope read as blotches of lit and shadowed canopy; Hong Kong's Peak from TST)
    if (CARPET_NORMALS) g.computeVertexNormals();
    g.computeBoundingSphere();
    const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.95 });
    // canopy texture as seen from afar: crowns (~10 m) and stands (~80 m) of lighter and darker green
    // crowns: Worley cells about 9 m across, lit tops and dark gaps between them, fading to their mean where a
    // crown is under a pixel (it would shimmer); stands of lighter and darker green over ~80 m
    const cdist = positionWorld.distance(cameraPosition);
    const crownK = float(1).sub(smoothstep(float(2500), float(9000), cdist));
    const crowns = mx_worley_noise_float(vec2(positionWorld.x, positionWorld.z).mul(1 / 9)).clamp(0, 1);
    // (city.json trees.carpetBranch, opt-in: the crowns' Worley noise only where they show, in a branch: beyond 9 km
    // crownK is 0 and the mix 1, so the picture is the same, without a Worley lookup per far pixel; Hong Kong M6)
    const crownL = CARPET_BRANCH ? Fn(() => {
      const l = float(1).toVar();
      If(cdist.lessThan(9000), () => { l.assign(mix(float(1), float(1.25).sub(crowns.mul(0.75)), crownK)); });
      return l;
    })() : mix(float(1), float(1.25).sub(crowns.mul(0.75)), crownK);
    const canopy = crownL.mul(mx_noise_float(positionWorld.mul(0.013)).mul(0.22).add(1));
    m.colorNode = vertexColor().mul(canopy);
    if (BLEND) {
      // (trees.carpetBlend: tint and glow as uniforms, for tuning from the console: __viewer.trees.blend)
      blend.tint = uniform(new THREE.Vector3(...(BLEND.tint ?? [1, 1, 1])));
      blend.glow = uniform(BLEND.glow ?? 0);
      // The impostor colours, the tint and the glow only where the carpet takes over from the trees: they ramp in
      // over `glowRamp` [from, to] m from the camera (the dissolve band, FAR - fade .. FAR, by default) and nearer
      // the carpet is the stands' dark floor with its own colours, lit and shadowed as ground. Applied everywhere,
      // the glow (an emissive term, blind to shadows) lit the whole floor 600 m+ out as a bright lawn with the
      // shadowed holes near-black: the Peak's hillside from TST at 15:00 (critic M7 round 2)
      const [g0, g1] = BLEND.glowRamp ?? [FAR - FAR_FADE, FAR];
      blend.ramp = smoothstep(float(g0), float(g1), positionWorld.distance(U.camPos));
      m.colorNode = mix(attribute('color0', 'vec3'), vertexColor().mul(blend.tint), blend.ramp).mul(canopy);
      if (BLEND.glow) m.emissiveNode = translucency(m.colorNode, normalWorld).mul(blend.glow.div(0.55)).mul(blend.ramp);
    }
    // Near the camera the carpet's straight polygon edges would show between the trees, so there the
    // ground is left bare (the trees' shadows darken it). Closed stands get their dark floor from about
    // a kilometre, where they are thinned out; parks and scrub, with their clearings, only as canopy
    // where the trees fade out.
    const dist = positionWorld.distance(U.camPos);
    const under = smoothstep(600, 1200, dist).mul(attribute('dense', 'float'));
    m.maskNode = max(under, smoothstep(FAR - FAR_FADE, FAR, dist)).greaterThanEqual(dither.mul(0.98).add(0.01));
    const carpet = new THREE.Mesh(g, m);
    carpet.receiveShadow = true;
    carpet.name = 'carpet';
    group.add(carpet);
    invalidate({ shadows: true, redraw: true });
  }

  // models, leaf atlas, impostor bake
  const t0 = performance.now();
  const atlas = leafAtlas();
  const t1 = performance.now();
  const geoms = SPECIES.map((S, sp) => {
    const m = S.palm ? palm(sp, 11 + sp) : broadleaf(sp, 5 + sp * 3);
    const g = m.geometry();
    g.userData.box = m.box;
    return g;
  });
  const imp = await bakeImpostors(renderer, geoms, atlas);
  const timing = { atlasMs: Math.round(t1 - t0), bakeMs: Math.round(performance.now() - t1) };

  // instanced meshes: one per species near, and the impostors
  const quad = new THREE.BufferGeometry();
  quad.setAttribute('position', new THREE.Float32BufferAttribute([-1, -1, 0, 1, -1, 0, 1, 1, 0, -1, 1, 0], 3));
  quad.setIndex([0, 1, 2, 0, 2, 3]);
  const all = [];
  const make = (name, base, mat, shadow) => {
    const mesh = new THREE.Mesh(new THREE.InstancedBufferGeometry(), mat);
    mesh.frustumCulled = false;                    // culled per tile when refilled
    mesh.visible = false;                          // until it has instances
    mesh.castShadow = shadow;
    mesh.receiveShadow = true;
    mesh.userData = { base, cap: 0, n: 0, tree: null, look: null, tris: base.index.count / 3 };
    mesh.name = name;
    group.add(mesh);
    all.push(mesh);
    return mesh;
  };
  const near = SPECIES.map((S, sp) => make(`trees-${S.name}`, geoms[sp], nearMaterial(sp, atlas, 'lit'), true));
  // one impostor mesh for all species; it casts shadows too: in woods the crowns' shadows on each other
  // and on the floor are much of the canopy's texture, and a band where they stop would show
  make('trees-impostor', quad, impostorMaterial(imp.tex, imp.frames), true);
  function ensure(mesh, n) {                         // (re)allocate instance buffers for n trees
    const u = mesh.userData;
    if (n <= u.cap) return;
    u.cap = Math.ceil(n * 1.5 / 1024) * 1024;
    const g = new THREE.InstancedBufferGeometry();
    for (const k of Object.keys(u.base.attributes)) g.setAttribute(k, u.base.attributes[k]);
    g.setIndex(u.base.index);
    u.tree = new THREE.InstancedBufferAttribute(new Float32Array(u.cap * 4), 4);
    u.look = new THREE.InstancedBufferAttribute(new Float32Array(u.cap * 3), 3);
    u.tree.setUsage(THREE.DynamicDrawUsage);
    u.look.setUsage(THREE.DynamicDrawUsage);
    g.setAttribute('tree', u.tree);
    g.setAttribute('look', u.look);
    mesh.geometry.dispose();
    mesh.geometry = g;
  }

  // tiles: loaded when within reach, dropped when well out of it
  const tiles = index.tiles.map((t) => ({ ...t, state: 'idle', data: null }));
  let inflight = 0, needFill = true;
  // (the camera's height above the ground under it counts, not above the sea)
  let camGround = 0;
  const tileDist2 = (t, p) => {
    const dx = Math.max(t.x - p.x, 0, p.x - t.x - 1000), dz = Math.max(t.z - p.z, 0, p.z - t.z - 1000), dy = Math.max(p.y - camGround, 0);
    return dx * dx + dz * dz + dy * dy;
  };
  async function load(t) {
    t.state = 'loading';
    inflight++;
    try {
      const buf = await gunzip(await (await fetch(url + t.file)).arrayBuffer());
      if (t.state === 'loading') { t.data = tileTrees(buf, t, index.classes, index.cell, terrain.height, table, index.streetSpecies, index.speciesBits, index.heightQ, index.caps, streetLift, index.liftBit ?? 0); t.state = 'ready'; }
    } catch (e) {
      console.warn('trees: tile failed', t.file, e);
      t.state = 'failed';
    }
    inflight--;
    needFill = true;
    invalidate({ shadows: true, redraw: true });   // (an arrival, not a move: see main.js)
  }
  function stream(p) {
    const want = [];
    for (const t of tiles) {
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

  // refill the instance buffers from the loaded tiles near and in view: a first pass counts each tree
  // into its meshes (trees in the near/impostor fade band go into both), a second writes the buffers
  const frustum = new THREE.Frustum(), projView = new THREE.Matrix4(), box = new THREE.Box3();
  const stats = { near: 0, impostors: 0, tiles: 0, triangles: 0, draws: 0, ...timing };
  const NS = SPECIES.length, IMP = NS, SKIP = 255;
  function fill() {
    const p = camera.position;
    camera.updateMatrixWorld();
    projView.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    frustum.setFromProjectionMatrix(projView, camera.coordinateSystem, camera.reversedDepth);   // (the camera's own depth convention)
    const list = [];
    for (const t of tiles) {
      if (t.state !== 'ready' || tileDist2(t, p) > FAR ** 2) continue;
      box.min.set(t.x - 20, t.data.y0, t.z - 20);
      box.max.set(t.x + 1020, t.data.y1 + 40, t.z + 1020);
      if (frustum.intersectsBox(box)) list.push(t.data);
    }
    const counts = new Array(NS + 1).fill(0);
    const n2 = U.near.value ** 2, nf2 = (U.near.value - FADE) ** 2, f2 = FAR ** 2, thin2 = THIN_FROM ** 2;
    for (const d of list) {
      d.near ??= new Uint8Array(d.n);
      d.imp ??= new Uint8Array(d.n);
      d.grow ??= new Float32Array(d.n);
      for (let i = 0; i < d.n; i++) {
        const dx = d.x[i] - p.x, dz = d.z[i] - p.z, dy = d.h[i] * 0.5 + d.y[i] - p.y;
        const d2 = dx * dx + dz * dz + dy * dy;
        d.grow[i] = 1;
        d.near[i] = d.imp[i] = SKIP;
        if (d2 > f2) continue;
        if (d.rank[i] && d2 > thin2) {
          // far dense stands: keep a share falling with distance, widened to keep the canopy closed
          const keep = Math.max(0.22, (thin2 / d2) ** 0.75);
          if (d.rank[i] > keep) continue;
          d.grow[i] = Math.min(1.8, 1 / Math.sqrt(keep));
        }
        if (d2 < n2) { d.near[i] = d.sp[i]; counts[d.sp[i]]++; }
        if (d2 > nf2) { d.imp[i] = IMP; counts[IMP]++; }
      }
    }
    all.forEach((m, j) => { ensure(m, counts[j]); m.userData.n = 0; });
    const put = (u, d, i) => {
      const k = u.n++, g = d.grow[i];
      u.tree.array[k * 4] = d.x[i];
      u.tree.array[k * 4 + 1] = d.z[i];
      u.tree.array[k * 4 + 2] = d.h[i] * (g > 1 ? g ** 0.4 : 1);
      u.tree.array[k * 4 + 3] = d.w[i] * g;
      u.look.array[k * 3] = d.col[i];
      u.look.array[k * 3 + 1] = d.sp[i];
      u.look.array[k * 3 + 2] = d.y[i];
    };
    for (const d of list) {
      for (let i = 0; i < d.n; i++) {
        if (d.near[i] !== SKIP) put(all[d.near[i]].userData, d, i);
        if (d.imp[i] !== SKIP) put(all[d.imp[i]].userData, d, i);
      }
    }
    stats.triangles = stats.draws = 0;
    for (const m of all) {
      const u = m.userData;
      m.visible = u.n > 0;
      if (m.visible) { stats.draws++; stats.triangles += u.n * u.tris; }
      if (!u.tree) continue;
      m.geometry.instanceCount = u.n;
      for (const a of [u.tree, u.look]) {
        a.clearUpdateRanges();
        a.addUpdateRange(0, Math.max(1, u.n * a.itemSize));
        a.needsUpdate = true;
      }
    }
    stats.near = counts.slice(0, NS).reduce((a, b) => a + b, 0);
    stats.impostors = counts[IMP];
    stats.tiles = list.length;
  }

  // camera and sun uniforms for the shaders
  const sun = (() => { let s = null; scene.traverse((o) => { if (o.isDirectionalLight && !s) s = o; }); return s; })();
  const hemi = (() => { let s = null; scene.traverse((o) => { if (o.isHemisphereLight && !s) s = o; }); return s; })();
  const tmp = new THREE.Vector3();
  function uniforms() {
    camera.updateMatrixWorld();
    U.camPos.value.copy(camera.position);
    U.camRight.value.setFromMatrixColumn(camera.matrixWorld, 0);
    U.camUp.value.setFromMatrixColumn(camera.matrixWorld, 1);
    if (sun) {
      tmp.copy(sun.position).sub(sun.target.position);
      if (tmp.lengthSq() > 1e-6) {
        U.sunDir.value.copy(tmp.normalize());
        U.sunRight.value.crossVectors(new THREE.Vector3(0, 1, 0), U.sunDir.value);
        // a summer noon sun stands almost straight overhead at this latitude: keep some axis
        if (U.sunRight.value.lengthSq() < 1e-6) U.sunRight.value.set(1, 0, 0);
        U.sunRight.value.normalize();
        U.sunUp.value.crossVectors(U.sunDir.value, U.sunRight.value);
      }
      U.sunColor.value.copy(sun.color).multiplyScalar(sun.intensity);
    }
    // the day's sky light never falls below 0.35 (main.js's setSun); only dusk and night dim it
    if (hemi) U.skyK.value = Math.min(1, hemi.intensity / 0.35);
  }

  // refill when tiles arrived or the camera has moved or turned enough; while it moves at most every
  // REFILL_MS (the frame drawn once the view settles always gets a refill if one is due)
  const REFILL_MS = 150;
  const lastPos = new THREE.Vector3(Infinity, 0, 0), lastQuat = new THREE.Quaternion();
  let lastFill = 0;
  function update(moving) {
    if (!group.visible) return;
    uniforms();
    const p = camera.position;
    camGround = terrain.height(p.x, p.z);
    stream(p);
    const moved = p.distanceTo(lastPos) > Math.max(8, 0.03 * (p.y - camGround));
    const turned = camera.quaternion.angleTo(lastQuat) > 0.04;
    const now = performance.now();
    if (!(needFill || moved || turned) || (moving && now - lastFill < REFILL_MS)) return;
    fill();
    needFill = false;
    lastFill = now;
    lastPos.copy(p);
    lastQuat.copy(camera.quaternion);
  }

  // the near-tree distance can be changed at run time (e.g. lower on a weak GPU, or 0 to compare impostors)
  const setNear = (d) => { U.near.value = Math.max(FADE, d); needFill = true; invalidate({ shadows: true }); };
  return { group, update, stats, meshes: all, index, atlas, impostors: imp, setNear, loadCarpet, blend };
}
