// Water (TSL): the open sea and the inland rivers, lakes, ponds and reservoirs. It moves (setWaterTime,
// see "motion" below: waves drift down-wind, gusts sweep across, rivers flow), but main.js only redraws
// it at a throttled rate while it is in view (waterInView), so the rest of the realism is in each frame:
//   - waves: two small tileable slope textures made here (sums of sines: a long-crested and a choppy
//     wind sea), read at five scales and angles, each domain-warped and with its own slowly wandering
//     strength so neither the tiles nor the wave trains repeat; their mipmaps also carry the mean squared
//     slope, so waves too small for a pixel turn into roughness (LEAN mapping, simplified) instead of
//     shimmer: the sun's glitter path widens and the water goes smooth with distance as in photographs.
//     Ponds are stillest, rivers a little less, the sheltered strip along seawalls calmer than the bay,
//     and harbour basins, marinas and coves (short fetch: little open water upwind) calm, dark and
//     mirror-like;
//   - calm patches ("slicks") and meandering wind streaks from a second, very low-frequency texture;
//   - the city mirrored: a planar reflection pass (renderWaterReflection, called by main.js before each
//     render) of buildings, trees and bridges, shifted by the resolved wave slopes and smeared into
//     vertical streaks and blurrier mips by the unresolved ones; crisp in ponds, a dark blurred band
//     under the far shore on the bay;
//   - sky reflection from the sky PMREM where nothing is mirrored, Schlick Fresnel with water's F0 = 0.02,
//     added as emission (like the glass in facade.js); the Mie glow round the sun is compressed softly,
//     since the glint itself is the directional light's own specular (so it is shadowed);
//   - body colour: what the water scatters back, lit as flat water whatever the wave normals do (so the
//     body itself doesn't ripple like crumpled foil) and weighted by 1 - Fresnel. The sea has one colour
//     along the shore, another near it and a third offshore, with plumes of silt and darker basins; rivers
//     and lakes have their own (configureWater; the defaults are Shenzhen's: the Pearl River estuary silty
//     grey-green-brown, rivers murky green-brown, ponds dark bottle green with patches of algae). The
//     shore distance comes from
//     a signed distance field rasterised on the CPU from ground.glb when it loads (shoreField below), which
//     also finds which inland water opens onto the sea (river mouths take the sea's colour) and which is a
//     compact pond rather than a river (seaLinks).
// Shorelines themselves (seawalls, revetments, mudflats, banks) are separate strips: shores.js.
// Haze: inland water takes the scene fog like every node material; the sea applies the same FogExp2
// itself so that far out, near the horizon, it can fade into the sky instead (no seam at the horizon).
import * as THREE from 'three/webgpu';
import {
  float, vec2, vec3, vec4, texture, positionWorld, positionView, cameraPosition, cameraViewMatrix, pmremTexture,
  output, mix, smoothstep, max, pow, sqrt, abs, fwidth, uniform, screenUV, attribute,
} from 'three/tsl';

// deterministic random numbers, so every load (and every screenshot) looks the same
function rng(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------- wave slope texture
// Sum of sines with whole wave numbers per tile, so it repeats seamlessly. Slopes are stored, not heights:
// rg = slope (x, z) mapped from [-S, S], ba = slope squared / S^2. Averaging in the mipmaps is linear in
// both, so a mip level holds the mean slope and the mean squared slope of the waves it covers; their
// difference is the slope variance that the pixel can no longer resolve.
const WAVE_SIZE = 256;
// direction the waves travel, as an angle in the scene's x-z plane (north is -z), from the compass direction
// the wind blows from (configureWater; by default from the south-west, towards the north-east: Shenzhen's
// before the summer monsoon)
const windAngle = (fromDeg) => THREE.MathUtils.degToRad(((fromDeg + 270) % 360) - 180);
let WIND = windAngle(225);
// seed: a different sea for each texture; spread: directional spread of the components (radians, about
// the standard deviation). A narrow spread makes long crests; a wide one short-crested, choppy water.
function waveTexture(seed, spread0) {
  const rand = rng(seed);
  const comps = [];
  for (let i = 0; i < 64; i++) {
    const k = 3 * Math.pow(16, rand());                            // 3..48 waves per tile, log-uniform
    // mostly down-wind, a few cross and opposing waves for irregularity
    const spread = (rand() + rand() + rand() - 1.5) * 2 * (rand() < 0.1 ? 2.6 * spread0 : spread0);
    const a = WIND + spread;
    const n = Math.round(k * Math.cos(a)), m = Math.round(k * Math.sin(a));
    if (n === 0 && m === 0) continue;
    const slope = Math.pow(Math.hypot(n, m), -0.3) * (0.6 + 0.8 * rand());   // steepness falls slowly with k
    comps.push({ kx: 2 * Math.PI * n, kz: 2 * Math.PI * m, s: slope, ph: 2 * Math.PI * rand() });
  }
  const N = WAVE_SIZE, sx = new Float32Array(N * N), sz = new Float32Array(N * N);
  let sum2 = 0;
  for (let j = 0; j < N; j++) {
    for (let i = 0; i < N; i++) {
      const u = i / N, v = j / N;
      let gx = 0, gz = 0;
      for (const c of comps) {
        const d = Math.sin(c.kx * u + c.kz * v + c.ph) * c.s;       // d/dx of cos(...) up to the amplitude
        gx -= d * c.kx; gz -= d * c.kz;
      }
      sx[j * N + i] = gx; sz[j * N + i] = gz;
      sum2 += gx * gx + gz * gz;
    }
  }
  const rms = Math.sqrt(sum2 / (2 * N * N));                        // per axis: normalise to 1
  let S = 0;
  for (let p = 0; p < N * N; p++) { sx[p] /= rms; sz[p] /= rms; S = Math.max(S, Math.abs(sx[p]), Math.abs(sz[p])); }
  const data = new Uint8Array(N * N * 4);
  for (let p = 0; p < N * N; p++) {
    data[p * 4] = Math.round((sx[p] / S * 0.5 + 0.5) * 255);
    data[p * 4 + 1] = Math.round((sz[p] / S * 0.5 + 0.5) * 255);
    data[p * 4 + 2] = Math.round((sx[p] * sx[p]) / (S * S) * 255);
    data[p * 4 + 3] = Math.round((sz[p] * sz[p]) / (S * S) * 255);
  }
  const tex = new THREE.DataTexture(data, N, N, THREE.RGBAFormat, THREE.UnsignedByteType);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.magFilter = THREE.LinearFilter;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.generateMipmaps = true;
  tex.anisotropy = 8;
  tex.colorSpace = THREE.NoColorSpace;
  tex.needsUpdate = true;
  return { tex, S };
}

// ---------------------------------------------------------------- low-frequency patches
// r: wind / calm patches, g: silt, b: a second wind scale. Smooth tileable noise (a few long sines).
function patchTexture() {
  const rand = rng(77031);
  const N = 128, data = new Uint8Array(N * N * 4);
  const chans = [0, 1, 2].map(() => Array.from({ length: 14 }, () => {
    const k = 1 + Math.floor(rand() * 5), a = rand() * 2 * Math.PI;
    return { n: Math.round(k * Math.cos(a)), m: Math.round(k * Math.sin(a)), ph: rand() * 2 * Math.PI, w: 1 / k };
  }));
  const vals = chans.map(() => new Float32Array(N * N));
  chans.forEach((comps, ch) => {
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
      let s = 0;
      for (const c of comps) s += c.w * Math.sin(2 * Math.PI * (c.n * i + c.m * j) / N + c.ph);
      vals[ch][j * N + i] = s;
    }
    let lo = Infinity, hi = -Infinity;
    for (const x of vals[ch]) { lo = Math.min(lo, x); hi = Math.max(hi, x); }
    for (let p = 0; p < N * N; p++) data[p * 4 + ch] = Math.round((vals[ch][p] - lo) / (hi - lo) * 255);
  });
  for (let p = 0; p < N * N; p++) data[p * 4 + 3] = 255;
  const tex = new THREE.DataTexture(data, N, N, THREE.RGBAFormat, THREE.UnsignedByteType);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.magFilter = THREE.LinearFilter;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.generateMipmaps = true;
  tex.colorSpace = THREE.NoColorSpace;
  tex.needsUpdate = true;
  return tex;
}

// ---------------------------------------------------------------- shore distance field
// Signed distance to the shore over the tile extent (positive on water, metres), from the ground layers:
// land, mud, green and aeroway are land, water polygons (drawn over them) are water, and whatever the ground
// does not cover is sea. r = distance within +-SHORE_NEAR m, g = 0..SHORE_FAR m on the water side,
// b = fetch 0..FETCH_MAX m (open water upwind: harbour basins and coves are calm, see buildWater),
// a = distance to the open sea 0..SEA_REACH m (tidal canals and river mouths take on the sea's colour
// and waves).
const SDF_W = 1024, SDF_H = 1536;
const SHORE_NEAR = 300, SHORE_FAR = 8000, SEA_REACH = 3000, FETCH_MAX = 5000;
const shoreTex = (() => {
  const data = new Uint8Array(SDF_W * SDF_H * 4).fill(255);            // until ground.glb arrives: open sea
  const tex = new THREE.DataTexture(data, SDF_W, SDF_H, THREE.RGBAFormat, THREE.UnsignedByteType);
  tex.magFilter = THREE.LinearFilter;
  tex.minFilter = THREE.LinearFilter;
  tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
  tex.colorSpace = THREE.NoColorSpace;
  tex.needsUpdate = true;
  return tex;
})();
const shoreBox = uniform(new THREE.Vector4(0, 0, 1, 1));            // xmin, zmin, width, depth (metres)

// 1D squared Euclidean distance transform (Felzenszwalb & Huttenlocher), in place on f[off + i*stride]
function edt1d(f, off, stride, n, v, z, d) {
  let k = 0;
  v[0] = 0; z[0] = -Infinity; z[1] = Infinity;
  for (let q = 1; q < n; q++) {
    const fq = f[off + q * stride];
    let s;
    for (;;) {
      const p = v[k];
      s = ((fq + q * q) - (f[off + p * stride] + p * p)) / (2 * q - 2 * p);
      if (s > z[k]) break;
      k--;
    }
    k++; v[k] = q; z[k] = s; z[k + 1] = Infinity;
  }
  k = 0;
  for (let q = 0; q < n; q++) {
    while (z[k + 1] < q) k++;
    const p = v[k];
    d[q] = (q - p) * (q - p) + f[off + p * stride];
  }
  for (let q = 0; q < n; q++) f[off + q * stride] = d[q];
}
// squared distance (pixels) from every pixel to the nearest pixel where site(mask) is true
function edt2d(mask, site) {
  const W = SDF_W, H = SDF_H, BIG = 1e12;
  const f = new Float64Array(W * H);
  for (let p = 0; p < W * H; p++) f[p] = site(mask[p]) ? 0 : BIG;
  const n = Math.max(W, H);
  const v = new Int32Array(n), z = new Float64Array(n + 1), d = new Float64Array(n);
  for (let i = 0; i < W; i++) edt1d(f, i, W, H, v, z, d);
  for (let j = 0; j < H; j++) edt1d(f, j * W, 1, W, v, z, d);
  return f;
}

// Fetch (metres of open water upwind, 0..FETCH_MAX) for every pixel of the mask (1 = land), averaged over FETCH_DIRS
// wind directions spread FETCH_SPREAD either side of the wind (weights cos^2). Each direction is one semi-Lagrangian
// sweep along its major pixel axis: a pixel's run is its upwind neighbour's, read between the two pixels of the
// previous column (or row) the ray passes, plus the step; land resets it, beyond the extent's edge is open sea.
// (It was three sweeps along the nearest grid directions, the wind's octant and the axes either side of it, whose
// lee shadows ran 1-2 km out from every pier and headland with straight, hard edges, half of them along the grid's
// axes: the basins' darker, calmer water stood out on the open sea as wedges and tile-aligned rectangles, Singapore
// M3 "two surfaces with a straight seam" off Tanjong Pagar. With the directions spread and the interpolation's
// blur, a lee now fades out sideways as it would under a wind that veers.)
const FETCH_DIRS = 9, FETCH_SPREAD = Math.PI / 4;
// (on a grid of half the field's resolution, a pixel land where any of its four is, so a breakwater one pixel wide
// still shelters: the fetch only matters over hundreds of metres; each sweep in the memory order of its major axis,
// columns over a transposed copy; read back with bilinear filtering. ~2.3 sweeps of the full grid in all, where the
// three full-resolution sweeps were 3)
function fetchField(mask, sx, sz) {
  const W = SDF_W, H = SDF_H, w = W >> 1, h = H >> 1, n = w * h;
  const hx = sx * 2, hz = sz * 2;
  const landR = new Uint8Array(n), landC = new Uint8Array(n);       // row-major (j, i) and column-major (i, j)
  for (let j = 0; j < h; j++) {
    for (let i = 0; i < w; i++) {
      const q = 2 * j * W + 2 * i;
      const l = mask[q] === 1 || mask[q + 1] === 1 || mask[q + W] === 1 || mask[q + W + 1] === 1 ? 1 : 0;
      landR[j * w + i] = l; landC[i * h + j] = l;
    }
  }
  const accR = new Float32Array(n), accC = new Float32Array(n), run = new Float32Array(n);
  let wsum = 0;
  for (let k = 0; k < FETCH_DIRS; k++) {
    const t = (k / (FETCH_DIRS - 1) * 2 - 1) * FETCH_SPREAD, wgt = Math.cos(t) ** 2;
    wsum += wgt;
    const dx = Math.cos(WIND + t), dz = Math.sin(WIND + t);       // downwind, metres
    // march along i (columns) when the ray crosses columns faster than rows, else along j
    const alongI = Math.abs(dx) / hx >= Math.abs(dz) / hz;
    const N = alongI ? w : h, M = alongI ? h : w;                   // steps along, pixels across
    const land = alongI ? landC : landR, acc = alongI ? accC : accR;
    const s = (alongI ? Math.sign(dx) : Math.sign(dz)) || 1;
    const len = alongI ? hx / Math.abs(dx) : hz / Math.abs(dz);     // metres per step
    const off = alongI ? dz * len / hz : dx * len / hx;             // pixels across per step, |off| <= 1
    const c0 = Math.floor(-off), f = -off - c0;                     // the upwind pixels: c + c0 and c + c0 + 1
    for (let aa = 0; aa < N; aa++) {
      const a = s > 0 ? aa : N - 1 - aa, row = a * M, prev = (a - s) * M, first = aa === 0;
      for (let c = 0; c < M; c++) {
        const p = row + c;
        if (land[p]) { run[p] = 0; continue; }
        let up = FETCH_MAX;
        if (!first) {
          const ca = c + c0, cb = ca + 1;
          const v0 = ca >= 0 && ca < M ? run[prev + ca] : FETCH_MAX;
          const v1 = cb >= 0 && cb < M ? run[prev + cb] : FETCH_MAX;
          up = v0 + (v1 - v0) * f;
        }
        const r = Math.min(up + len, FETCH_MAX);
        run[p] = r;
        acc[p] += wgt * r;
      }
    }
  }
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) accR[j * w + i] = (accR[j * w + i] + accC[i * h + j]) / wsum;
  // back to the full grid (pixel centres: full (i + 0.5) / 2 - 0.5 on the half grid)
  const fetch = new Float32Array(W * H);
  for (let j = 0; j < H; j++) {
    const y = Math.min(Math.max((j - 0.5) / 2, 0), h - 1), j0 = Math.min(Math.floor(y), h - 2), fy = y - j0;
    for (let i = 0; i < W; i++) {
      const x = Math.min(Math.max((i - 0.5) / 2, 0), w - 1), i0 = Math.min(Math.floor(x), w - 2), fx = x - i0;
      const q = j0 * w + i0;
      const top = accR[q] + (accR[q + 1] - accR[q]) * fx, bot = accR[q + w] + (accR[q + w + 1] - accR[q + w]) * fx;
      fetch[j * W + i] = top + (bot - top) * fy;
    }
  }
  return fetch;
}

// root: the loaded ground scene (meshes named by layer); extent: index.extent
export function shoreField(root, extent) {
  const t0 = performance.now();
  const W = SDF_W, H = SDF_H;
  const x0 = extent.xmin, z0 = extent.zmin, sx = (extent.xmax - extent.xmin) / W, sz = (extent.zmax - extent.zmin) / H;
  const mask = new Uint8Array(W * H);                                 // 0 = sea, 1 = land, 2 = inland water
  const layers = {};
  root.updateWorldMatrix(true, true);
  root.traverse((o) => { if (o.isMesh) layers[o.name] = o; });                 // meshes are named by layer
  const raster = (o, value) => {
    if (!o) return;
    const pos = o.geometry.attributes.position, idx = o.geometry.index, e = o.matrixWorld.elements;
    const n = idx ? idx.count : pos.count;
    const px = new Float32Array(pos.count), pz = new Float32Array(pos.count);
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
      px[i] = ((e[0] * x + e[4] * y + e[8] * z + e[12]) - x0) / sx - 0.5;   // pixel centres at integers
      pz[i] = ((e[2] * x + e[6] * y + e[10] * z + e[14]) - z0) / sz - 0.5;
    }
    for (let t = 0; t < n; t += 3) {
      const a = idx ? idx.getX(t) : t, b = idx ? idx.getX(t + 1) : t + 1, c = idx ? idx.getX(t + 2) : t + 2;
      const ax = px[a], az = pz[a], bx = px[b], bz = pz[b], cx = px[c], cz = pz[c];
      const area = (bx - ax) * (cz - az) - (bz - az) * (cx - ax);
      if (area === 0) continue;
      const sgn = area > 0 ? 1 : -1;
      const i0 = Math.max(0, Math.ceil(Math.min(ax, bx, cx))), i1 = Math.min(W - 1, Math.floor(Math.max(ax, bx, cx)));
      const j0 = Math.max(0, Math.ceil(Math.min(az, bz, cz))), j1 = Math.min(H - 1, Math.floor(Math.max(az, bz, cz)));
      for (let j = j0; j <= j1; j++) {
        for (let i = i0; i <= i1; i++) {
          const w0 = ((bx - ax) * (j - az) - (bz - az) * (i - ax)) * sgn;
          const w1 = ((cx - bx) * (j - bz) - (cz - bz) * (i - bx)) * sgn;
          const w2 = ((ax - cx) * (j - cz) - (az - cz) * (i - cx)) * sgn;
          if (w0 >= 0 && w1 >= 0 && w2 >= 0) mask[j * W + i] = value;
        }
      }
    }
  };
  // the intertidal mud (drawn over the sea) counts as shore: the water starts at its edge
  raster(layers.land, 1); raster(layers.mud, 1); raster(layers.green, 1); raster(layers.water, 2); raster(layers.aeroway, 1);
  const toLand = edt2d(mask, (m) => m === 1), toWater = edt2d(mask, (m) => m !== 1), toSea = edt2d(mask, (m) => m === 0);
  const texel = Math.sqrt(sx * sz);
  // Fetch: how much open water lies upwind, the stretch over which the wind raises its waves (see fetchField)
  const fetch = fetchField(mask, sx, sz);
  const data = shoreTex.image.data;
  for (let p = 0; p < W * H; p++) {
    // half a texel each side, so the zero crossing lies between a land and a water pixel
    const d = (mask[p] === 1 ? 0.5 - Math.sqrt(toWater[p]) : Math.sqrt(toLand[p]) - 0.5) * texel;
    data[p * 4] = Math.round(Math.min(Math.max(d / SHORE_NEAR * 0.5 + 0.5, 0), 1) * 255);
    data[p * 4 + 1] = Math.round(Math.min(Math.max(d / SHORE_FAR, 0), 1) * 255);
    data[p * 4 + 2] = Math.round(fetch[p] / FETCH_MAX * 255);
    data[p * 4 + 3] = Math.round(Math.min(Math.sqrt(toSea[p]) * texel / SEA_REACH, 1) * 255);
  }
  shoreTex.needsUpdate = true;
  shoreBox.value.set(x0, z0, extent.xmax - x0, extent.zmax - z0);
  // where there is water at all, for the reflection pass (renderWaterReflection): the raster plus the
  // texels of every water vertex (ponds smaller than a texel), grown by a texel
  const wet = new Uint8Array(W * H);
  for (let p = 0; p < W * H; p++) wet[p] = mask[p] !== 1 ? 1 : 0;
  if (layers.water) {
    const pos = layers.water.geometry.attributes.position, e = layers.water.matrixWorld.elements;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
      const pi = Math.round(((e[0] * x + e[4] * y + e[8] * z + e[12]) - x0) / sx - 0.5);
      const pj = Math.round(((e[2] * x + e[6] * y + e[10] * z + e[14]) - z0) / sz - 0.5);
      if (pi >= 0 && pi < W && pj >= 0 && pj < H) wet[pj * W + pi] = 1;
    }
  }
  const grown = new Uint8Array(W * H);
  for (let j = 0; j < H; j++) {
    for (let i = 0; i < W; i++) {
      let v = 0;
      for (let dj = -1; dj <= 1 && !v; dj++) for (let di = -1; di <= 1 && !v; di++) {
        const a = i + di, b = j + dj;
        if (a >= 0 && a < W && b >= 0 && b < H && wet[b * W + a]) v = 1;
      }
      grown[j * W + i] = v;
    }
  }
  waterGrid = { data: grown, x0, z0, sx, sz };
  _inView.key = null;
  const seaDist = (x, z) => {
    const i = Math.min(W - 1, Math.max(0, Math.round((x - x0) / sx - 0.5)));
    const j = Math.min(H - 1, Math.max(0, Math.round((z - z0) / sz - 0.5)));
    return Math.sqrt(toSea[j * W + i]) * texel;
  };
  if (layers.water) seaLinks(layers.water, seaDist, 2.5 * texel, 2 * Math.max(sx, sz));
  return performance.now() - t0;
}

// Which inland water opens onto the sea, and which is a pond. Each connected piece of the water mesh
// (triangles sharing vertices: one polygon, or rivers welded where they meet) that comes within `reach`
// of open sea is linked: river mouths and tidal canals take on the sea's colour and waves near it, a
// pond a few hundred metres inland must not. A piece that is compact (area over its bounding box's
// squared diagonal) is a pond or lake: still, dark water; a long thin one a river or canal. Result: the
// per-vertex attribute 'waterKind' = (sea link 0/1, pondness 0..1).
// Also the current (attribute 'waterFlow', m/s in x, z) that carries the ripples of rivers and canals
// (see buildWater): every vertex of the water mesh lies on a polygon's outline, so the two outline
// edges through it run along the bank, i.e. along the channel. Their direction is an axis without a
// sign (the outline runs down one bank and back up the other), averaged as a doubled angle; the sign
// is downstream, taken as the way the distance to the open sea falls (h metres for the gradient).
function seaLinks(mesh, toSea, reach, h) {
  const g = mesh.geometry, pos = g.attributes.position, idx = g.index, e = mesh.matrixWorld.elements;
  const n = pos.count, parent = new Int32Array(n);
  for (let i = 0; i < n; i++) parent[i] = i;
  const find = (i) => { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; } return i; };
  const tris = idx ? idx.count : n;
  const vi = (t) => (idx ? idx.getX(t) : t);
  for (let t = 0; t < tris; t += 3) {
    const a = find(vi(t));
    for (const k of [1, 2]) { const b = find(vi(t + k)); if (a !== b) parent[b] = a; }
  }
  const wx = new Float64Array(n), wz = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    wx[i] = e[0] * x + e[4] * y + e[8] * z + e[12];
    wz[i] = e[2] * x + e[6] * y + e[10] * z + e[14];
  }
  const linked = new Uint8Array(n), area = new Float64Array(n);
  const lo = new Float64Array(2 * n).fill(Infinity), hi = new Float64Array(2 * n).fill(-Infinity);
  for (let i = 0; i < n; i++) {
    const r = find(i);
    if (toSea(wx[i], wz[i]) < reach) linked[r] = 1;
    lo[2 * r] = Math.min(lo[2 * r], wx[i]); hi[2 * r] = Math.max(hi[2 * r], wx[i]);
    lo[2 * r + 1] = Math.min(lo[2 * r + 1], wz[i]); hi[2 * r + 1] = Math.max(hi[2 * r + 1], wz[i]);
  }
  for (let t = 0; t < tris; t += 3) {
    const a = vi(t), b = vi(t + 1), c = vi(t + 2);
    area[find(a)] += Math.abs((wx[b] - wx[a]) * (wz[c] - wz[a]) - (wz[b] - wz[a]) * (wx[c] - wx[a])) / 2;
  }
  // outline edges: those used by one triangle only; their doubled angles (weighted by length) summed
  // at both ends
  const edges = new Map();
  for (let t = 0; t < tris; t += 3) {
    for (let k = 0; k < 3; k++) {
      const a = vi(t + k), b = vi(t + (k + 1) % 3);
      const key = a < b ? a * n + b : b * n + a;
      edges.set(key, (edges.get(key) ?? 0) + 1);
    }
  }
  const c2 = new Float64Array(n), s2 = new Float64Array(n);
  for (const [key, count] of edges) {
    if (count !== 1) continue;
    const a = Math.floor(key / n), b = key % n;
    const dx = wx[b] - wx[a], dz = wz[b] - wz[a], len = Math.hypot(dx, dz);
    if (len < 1e-6) continue;
    const c = (dx * dx - dz * dz) / len, s = 2 * dx * dz / len;          // len * (cos 2a, sin 2a)
    c2[a] += c; s2[a] += s; c2[b] += c; s2[b] += s;
  }
  const attr = new Float32Array(2 * n), flow = new Float32Array(2 * n), size = new Float32Array(n), still = new Float32Array(n);
  // still water (configureWater's inland.still, off by default): every piece under still.maxArea m² that
  // doesn't open onto the sea (impounded docks, park lakes, canal basins), the rest the turbid tidal river
  const stillMax = COLOURS.inland.still?.maxArea ?? 0;
  for (let i = 0; i < n; i++) {
    const r = find(i);
    const diag2 = (hi[2 * r] - lo[2 * r]) ** 2 + (hi[2 * r + 1] - lo[2 * r + 1]) ** 2;
    const c = area[r] / Math.max(diag2, 1);                      // a square 0.5, a disc 0.39, a canal ~0
    const pond = Math.min(Math.max((c - 0.06) / 0.12, 0), 1);
    attr[2 * i] = linked[r];
    attr[2 * i + 1] = pond;
    // small compact water (fountain basins, garden pools: under ~6,000 m², gone by 15,000): shallow, over a
    // stone floor (configureWater's inland.basin)
    size[i] = pond * Math.min(Math.max((15000 - area[r]) / 9000, 0), 1);
    still[i] = stillMax && (!linked[r] || COLOURS.inland.seaLink === false) ? Math.min(Math.max((stillMax - area[r]) / (0.2 * stillMax), 0), 1) : 0;
    // along the bank, downstream; rivers about 0.7 m/s, tidal canals slower, ponds still. Where the
    // channel runs across the way to the sea the sign is unsure, so the current fades out there
    // instead of flipping from one vertex to the next.
    const ang = Math.atan2(s2[i], c2[i]) / 2, ux = Math.cos(ang), uz = Math.sin(ang);
    const gx = toSea(wx[i] + h, wz[i]) - toSea(wx[i] - h, wz[i]);
    const gz = toSea(wx[i], wz[i] + h) - toSea(wx[i], wz[i] - h);
    const gl = Math.hypot(gx, gz);
    const along = gl > 1e-6 ? -(ux * gx + uz * gz) / gl : 0;           // cosine to downhill
    const sure = Math.min(Math.max((Math.abs(along) - 0.1) / 0.3, 0), 1);
    const speed = (linked[r] ? 0.4 : 0.7) * (1 - pond) * sure * Math.sign(along);
    flow[2 * i] = ux * speed;
    flow[2 * i + 1] = uz * speed;
  }
  g.setAttribute('waterKind', new THREE.BufferAttribute(attr, 2));
  g.setAttribute('waterFlow', new THREE.BufferAttribute(flow, 2));
  g.setAttribute('waterBasin', new THREE.BufferAttribute(size, 1));
  g.setAttribute('waterStill', new THREE.BufferAttribute(still, 1));
}

// ---------------------------------------------------------------- planar reflection
// The city mirrored in the water: the scene drawn once more, from the camera reflected in the plane
// y = MIRROR_Y, into a target of half the view's resolution, only when the view is redrawn anyway
// (on-demand rendering). Sky, water and everything flat on the ground are left out (meshes marked
// userData.noReflect: the ground layers, roads and markings, which follow the hills now): the sky reflection
// comes from the sky PMREM (so rough water can blur it by roughness), the ground would only be seen
// from below. The target is cleared to transparent, so its alpha says where a building, tree or bridge
// is mirrored. One plane serves the sea (y -1) and inland water on the plain (the ground's 0 to a few metres,
// plus 0.9): mirrored a few metres off, nobody can tell; water higher up takes no mirror (see buildWater).
// Cost control: the mirrored view only covers the part of the screen where water can be seen (a coarse
// grid of view rays against the water raster), so frustum culling drops whatever cannot be mirrored
// into it and that part gets all the target's pixels; with no water in view there is no pass at all.
// (configureWater's mirror: an inland city's main water level as drawn, the ground's pool plus the layer's 0.9;
// Paris's Seine 3.55 + 0.9. Water on other levels (canals above their locks) gets the banks' dark fallback)
let MIRROR_Y = 0;
const reflTarget = new THREE.RenderTarget(1, 1, { type: THREE.HalfFloatType, depthBuffer: true });
reflTarget.texture.generateMipmaps = true;              // blur levels for rough water
reflTarget.texture.minFilter = THREE.LinearMipmapLinearFilter;
reflTarget.texture.magFilter = THREE.LinearFilter;
const mirrorCam = new THREE.PerspectiveCamera();
const reflSize = new THREE.Vector2();
const reflOn = uniform(0);                               // 0 until a reflection is drawn, or none in view
const reflRect = uniform(new THREE.Vector4(0, 0, 1, 1)); // screen uv (origin top left) the target covers
// the same as bounds (u0, v0, u1, v1) to fade out at, pushed off screen where the rectangle meets its edge
const reflFade = uniform(new THREE.Vector4(-1, -1, 2, 2));
let waterGrid = null;                                    // shoreField: where there is water at all
const flatCache = new WeakMap();
const _v = new THREE.Vector3(), _t = new THREE.Vector3(), _d = new THREE.Vector3(), _clear = new THREE.Color();
// meshes not worth mirroring: water itself, and flat ground layers (roads, markings, land), which the
// mirrored camera sees from below, where they are culled anyway after costing their vertices
function skipInReflection(o) {
  if (o.material?.userData?.water || o.userData.noReflect) return true;
  let flat = flatCache.get(o.geometry);
  if (flat === undefined) {
    const g = o.geometry;
    if (!o.isInstancedMesh && g) {
      if (!g.boundingBox) g.computeBoundingBox();
      flat = g.boundingBox.max.y - g.boundingBox.min.y < 0.5;
    } else flat = false;
    if (g) flatCache.set(g, flat);
  }
  return flat;
}

// The screen rectangle (uv, origin top left) in which water can be seen, or null: view rays on a
// GRID x GRID grid down to the ground, looked up in the water raster (outside it: open sea), the
// rectangle of the hits grown by a cell plus room for the wave distortion.
const GRID = 24;
const REFL_REACH = 12000;     // metres: water further away is mostly fog (FogExp2 7e-5: over half)
// (still: city.json water.mirrorLines, default 560: London's calm Thames showed the 560 lines' slope-shifted lookups as
// stair-stepped smears close up)
let REFL_LINES = 560;
const REFL_LINES_MOVING = 320;      // target height (pixels), still and moving
const REFL_TILES = 9000, REFL_TILES_MOVING = 4500;    // metres: tiles mirrored, still and moving
// (city.json water.mirrorCull, off by default: a tile is mirrored only if its mirror image, the box reflected in the
// plane and seen by the view's camera, covers a grid point where water was seen, give or take the rectangle's margin:
// the rest would mirror onto land. The grid points of the last waterRect)
let MIRROR_CULL = false;
// the layer of the building tiles' mirror stand-ins (main.js mirrorChunks, water.mirrorChunk): drawn by the mirror's
// camera alone, in place of their whole meshes, each over the runs of cells whose mirror image meets water
export const MIRROR_LAYER = 5;
const wetAt = new Uint8Array((GRID + 1) * (GRID + 1));
let wetCount = 0;
export function setMirrorCull(on) { MIRROR_CULL = on; }
function waterRect(camera, reach = REFL_REACH, count = null) {
  let u0 = 2, v0 = 2, u1 = -1, v1 = -1, hits = 0;
  wetAt.fill(0);
  camera.updateMatrixWorld();
  _v.setFromMatrixPosition(camera.matrixWorld);
  for (let j = 0; j <= GRID; j++) {
    for (let i = 0; i <= GRID; i++) {
      const u = i / GRID, v = j / GRID;
      _d.set(u * 2 - 1, 1 - v * 2, 0.5).unproject(camera).sub(_v);
      if (_d.y >= -1e-6 * _d.length()) continue;                  // above the horizon
      const t = (MIRROR_Y - _v.y) / _d.y;
      if (t * _d.length() > reach) continue;                       // lost in the haze anyway
      const x = _v.x + _d.x * t, z = _v.z + _d.z * t;
      let wet = 1;
      if (waterGrid) {
        const g = waterGrid;
        const pi = Math.floor((x - g.x0) / g.sx), pj = Math.floor((z - g.z0) / g.sz);
        if (pi >= 0 && pi < SDF_W && pj >= 0 && pj < SDF_H) wet = g.data[pj * SDF_W + pi];
      }
      if (!wet) continue;
      hits++;
      wetAt[j * (GRID + 1) + i] = 1;
      u0 = Math.min(u0, u); u1 = Math.max(u1, u); v0 = Math.min(v0, v); v1 = Math.max(v1, v);
    }
  }
  if (count) count.hits = hits / ((GRID + 1) * (GRID + 1));
  wetCount = hits;
  if (u1 < 0) return null;
  const m = 1 / GRID + 0.06;
  u0 = Math.max(0, u0 - m); v0 = Math.max(0, v0 - m); u1 = Math.min(1, u1 + m); v1 = Math.min(1, v1 + m);
  return [u0, v0, u1 - u0, v1 - v0];
}

// whether a box's mirror image (reflected in y = MIRROR_Y) as the view's camera sees it covers a grid point where water
// was seen (with waterRect's margin: a cell and the waves' distortion); anything partly behind the camera counts
const _p = new THREE.Vector3();
function mirrorSeen(box, camera) {
  let u0 = Infinity, v0 = Infinity, u1 = -Infinity, v1 = -Infinity;
  for (let k = 0; k < 8; k++) {
    _p.set(k & 1 ? box.max.x : box.min.x, 2 * MIRROR_Y - (k & 2 ? box.max.y : box.min.y), k & 4 ? box.max.z : box.min.z)
      .applyMatrix4(camera.matrixWorldInverse);
    if (_p.z > -camera.near) return true;
    _p.applyMatrix4(camera.projectionMatrix);
    const u = (_p.x + 1) / 2, v = (1 - _p.y) / 2;
    u0 = Math.min(u0, u); u1 = Math.max(u1, u); v0 = Math.min(v0, v); v1 = Math.max(v1, v);
  }
  const m = 1 / GRID + 0.06;
  const i0 = Math.max(0, Math.ceil((u0 - m) * GRID)), i1 = Math.min(GRID, Math.floor((u1 + m) * GRID));
  const j0 = Math.max(0, Math.ceil((v0 - m) * GRID)), j1 = Math.min(GRID, Math.floor((v1 + m) * GRID));
  for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) if (wetAt[j * (GRID + 1) + i]) return true;
  return false;
}
export const mirrorStats = { tiles: 0, culled: 0, chunks: 0, chunksCulled: 0 };
// a mesh's cells (main.js mirrorChunks: index ranges in row order, with world boxes): the runs of cells whose mirror
// image meets water, at most as many as the mesh has stand-ins (the closest runs merged, cells between them drawn too)
function mirrorRuns({ cells, meshes }, camera) {
  const runs = [];
  for (const c of cells) {
    mirrorStats.chunks++;
    if (!mirrorSeen(c.box, camera)) { mirrorStats.chunksCulled++; continue; }
    const last = runs.at(-1);
    if (last && last[1] === c.start) last[1] = c.start + c.count; else runs.push([c.start, c.start + c.count]);
  }
  while (runs.length > meshes.length) {
    let k = 0;
    for (let i = 1; i < runs.length - 1; i++) if (runs[i + 1][0] - runs[i][1] < runs[k + 1][0] - runs[k][1]) k = i;
    runs[k][1] = runs[k + 1][1];
    runs.splice(k + 1, 1);
  }
  meshes.forEach((m, i) => {
    m.visible = i < runs.length;
    if (m.visible) m.geometry.setDrawRange(runs[i][0], runs[i][1] - runs[i][0]);
  });
}

// Draw the mirrored scene; call before each render of the view. hide: extra objects to leave out (the
// sky). moving: the view is on the move (a coarser target). Returns the milliseconds spent on the CPU.
export function renderWaterReflection(renderer, scene, camera, { hide = [], moving = false } = {}) {
  const t0 = performance.now();
  const rect = waterRect(camera);
  if (!rect) {
    reflOn.value = 0;
    return performance.now() - t0;
  }
  renderer.getDrawingBufferSize(reflSize);
  // at most half the drawing buffer, and no taller than REFL_LINES (moving: fewer): the waves blur the
  // mirror image anyway, and on a 2x display half resolution would be as many pixels as the view in CSS
  const scale = Math.min(moving ? 0.35 : 0.5, (moving ? REFL_LINES_MOVING : REFL_LINES) / reflSize.y);
  // only the water rectangle needs pixels; sizes in steps of 64 so the target is not remade every frame
  const step = (x) => Math.max(64, Math.ceil(x / 64) * 64);
  const w = step(reflSize.x * scale * rect[2]), h = step(reflSize.y * scale * rect[3]);
  if (reflTarget.width !== w || reflTarget.height !== h) reflTarget.setSize(w, h);
  // mirror the camera: position and look-at point reflected in the plane, up vector too (the image comes
  // out flipped left-right, which the lookup undoes)
  mirrorCam.copy(camera);
  _v.setFromMatrixPosition(camera.matrixWorld);
  mirrorCam.position.set(_v.x, 2 * MIRROR_Y - _v.y, _v.z);
  _t.set(0, 0, -1).transformDirection(camera.matrixWorld).add(_v);
  _t.y = 2 * MIRROR_Y - _t.y;
  mirrorCam.up.set(0, 1, 0).transformDirection(camera.matrixWorld);
  mirrorCam.up.y = -mirrorCam.up.y;
  mirrorCam.lookAt(_t);
  mirrorCam.updateMatrixWorld();
  // only the water's part of the view (mirrored left-right)
  const [u0, v0, du, dv] = rect;
  const W = reflSize.x, H = reflSize.y;
  mirrorCam.setViewOffset(W, H, (1 - u0 - du) * W, v0 * H, du * W, dv * H);
  reflRect.value.set(u0, v0, du, dv);
  reflFade.value.set(u0 > 0 ? u0 : -1, v0 > 0 ? v0 : -1, u0 + du < 1 ? u0 + du : 2, v0 + dv < 1 ? v0 + dv : 2);

  const hidden = [];
  for (const o of hide) if (o.visible) { o.visible = false; hidden.push(o); }
  // tiles (main.js tags their groups with userData.tile) further than the reach: their mirror images
  // would be a few hazy pixels, and each costs draw calls
  const reach = moving ? REFL_TILES_MOVING : REFL_TILES;
  mirrorStats.tiles = mirrorStats.culled = mirrorStats.chunks = mirrorStats.chunksCulled = 0;
  if (MIRROR_CULL) mirrorCam.layers.enable(MIRROR_LAYER);
  scene.traverseVisible((o) => {
    if (o.userData.mirrorRun) return;
    if (o.userData.mirrorRuns && MIRROR_CULL) { mirrorRuns(o.userData.mirrorRuns, camera); hidden.push(o); return; }
    const t = o.userData.tile;
    if (t) {
      const dx = t.x + t.size / 2 - _v.x, dz = t.z + t.size / 2 - _v.z;
      if (dx * dx + dz * dz > reach * reach) hidden.push(o);
      else if (MIRROR_CULL) {
        mirrorStats.tiles++;
        // (the group's box, once: its meshes' bounds are kept when their arrays are freed)
        const box = o.userData.mirrorBox ??= new THREE.Box3().setFromObject(o);
        if (!box.isEmpty() && !mirrorSeen(box, camera)) { hidden.push(o); mirrorStats.culled++; }
      }
    } else if (o.isMesh && skipInReflection(o)) hidden.push(o);
  });
  for (const o of hidden) o.visible = false;
  const rt = renderer.getRenderTarget(), mrt = renderer.getMRT();
  renderer.getClearColor(_clear);
  const alpha = renderer.getClearAlpha();
  renderer.setMRT(null);
  renderer.setRenderTarget(reflTarget);
  renderer.setClearColor(0x000000, 0);
  renderer.clear();
  renderer.render(scene, mirrorCam);
  renderer.setRenderTarget(rt);
  renderer.setMRT(mrt);
  renderer.setClearColor(_clear, alpha);
  for (const o of hidden) o.visible = true;
  reflOn.value = 1;
  return performance.now() - t0;
}
// switched off, the water shows only the sky until renderWaterReflection runs again
export function setWaterReflection(on) {
  if (!on) reflOn.value = 0;
}

// ---------------------------------------------------------------- motion
// The water moves (main.js redraws it at a throttled rate while it is in view, see waterInView): every
// wave scale drifts down-wind at the phase speed of its waves (deep water, c = sqrt(g L / 2 pi): long
// waves outrun short ones, so the pattern changes as it moves instead of sliding as one sheet), gusts
// (each scale's wandering strength) sweep across at about the wind's speed, the calm slicks and wind
// streaks creep with the surface drift, and rivers and canals carry their ripples downstream (the
// 'waterFlow' current, by the usual two-phase flow-map blend so the pattern never stretches).
// All offsets are wrapped on the CPU to one repeat of their texture, so the time can grow forever.
const ANIM_REACH = 5000;           // metres: moving water further away than this is lost in the haze
const ANIM_MIN = 0.04;             // share of the view (of the coarse ray grid) that must be such water
const FLOW_PERIOD = 5;             // seconds per flow-map phase
const GUST_SPEED = 3.5, DRIFT_SPEED = 0.25;   // m/s: gusts, surface drift of slicks and streaks
const layerShift = [];             // per wave scale: uv offset of its slope texture (buildWater)
const gustShift = [];              // per wave scale: uv offset of its strength patches
const slickShift = uniform(new THREE.Vector3());  // uv offsets of the calm/wind patches (p1: xy, p2: z)
const flowPhase = uniform(new THREE.Vector2(0.25, 0.75));
const _inView = { key: null, share: 0, m: new Float64Array(32) };

// Share of the view (0..1) showing water close enough for its motion to be seen. Cached while the
// camera stands still, which is when it is asked every frame.
export function waterInView(camera) {
  camera.updateMatrixWorld();
  const a = camera.matrixWorld.elements, b = camera.projectionMatrix.elements, m = _inView.m;
  let same = _inView.key !== null;
  for (let i = 0; i < 16; i++) {
    if (m[i] !== a[i] || m[16 + i] !== b[i]) same = false;
    m[i] = a[i]; m[16 + i] = b[i];
  }
  if (!same) {
    const count = { hits: 0 };
    waterRect(camera, ANIM_REACH, count);
    _inView.share = count.hits;
    _inView.key = true;
  }
  return _inView.share >= ANIM_MIN ? _inView.share : 0;
}

// seconds of water time: sets every drift and flow phase
export function setWaterTime(t) {
  if (!LAYERS) configureWater();
  const wc = Math.cos(WIND), ws = Math.sin(WIND), fr = (x) => x - Math.floor(x);
  LAYERS.forEach((L, i) => {
    // down-wind in the texture's own axes (its waves run along WIND there); sampling at uv - d moves
    // the pattern by +d
    const c = Math.sqrt(9.81 * (L.size / 12) / (2 * Math.PI));
    const d = c * t / L.size;
    layerShift[i].value.set(-fr(wc * d), -fr(ws * d));
    const g = GUST_SPEED * t / (L.size * 17 + 400);
    gustShift[i].value.set(-fr(wc * g), -fr(ws * g));
  });
  const s = DRIFT_SPEED * t;
  slickShift.value.set(-fr(wc * s / 6100), -fr(ws * s / 6100), -fr(s / 3900));
  const p = t / FLOW_PERIOD;
  flowPhase.value.set(fr(p), fr(p + 0.5));
}

// ---------------------------------------------------------------- shared shading
const patches = patchTexture();
// five wave scales (made by configureWater), each turned so the repeats never line up, alternating two
// textures: tile size (m), turn (rad), slope weight (rms per axis), how much the calm/wind patches affect
// it, and a domain warp (m): each layer is shifted by a slowly varying offset, so neither its tiling nor
// its diagonal wave trains repeat over the bay. Each layer's strength also wanders on its own (cat's paws,
// lulls).
let LAYERS = null;
for (let i = 0; i < 5; i++) {
  layerShift.push(uniform(new THREE.Vector2()));
  gustShift.push(uniform(new THREE.Vector2()));
}
// (city.json water.mirrorBlur: the mirror's least blur (mip level) and its taps staggered sideways; 0: none)
let MIRROR_BLUR = 0;
// the water's colours (linear albedo) and how much of the reflected sky's colour is kept (configureWater)
let COLOURS = {
  sea: { shore: [0.105, 0.106, 0.082], near: [0.08, 0.094, 0.078], offshore: [0.066, 0.08, 0.082],
    silt: [0.14, 0.128, 0.088], basin: [0.048, 0.064, 0.054] },
  inland: { river: [0.036, 0.046, 0.03], lake: [0.011, 0.024, 0.018], basin: null, skyTint: null,
    // (London M5 fix round) the turbid river's look: how much of the physical reflection (sky and mirrored city) it
    // keeps, and its waves' share of the sea's (0.25: sheltered); still water ({ maxArea m², body linear rgb,
    // reflect, waves, banks: the dark-banks share where it lies off the mirror plane }; null: none, see seaLinks)
    riverReflect: 1, reflectGrazing: null, riverWaves: 0.25, still: null, seaLink: true },
  skySaturation: { sea: 0.55, inland: 0.4 },
};

// The city's wind and water colours (city.json's water section), set before any water material is made:
// the wave textures are drawn for the wind (the same on every load: fixed seeds)
// night: { glow, sky, gain, max, streak, knee, base } (defaults 0.5, 1, 2, 2.5, 3, 0, 1): after dark the share of the city's sky glow
// added all over the water, the mirrored sky's strength, how much brighter the mirrored lights read (x (1 + gain x
// lights) where the water is dark), their cap, the streaks' length (x the ripples' smear), and with knee/base only
// the mirror brighter than knee boosted, the rest kept at base. London: a near-black
// Thames with long streaks (glow 0.08, sky 0.35, streak 5); Paris's defaults read as a milky brown sheet; floor
// [r, g, b]: the least light the water keeps (null: none)
export function configureWater({ windFrom = 225, sea = {}, inland = {}, skySaturation = {}, mirror = 0, mirrorBlur = 0, mirrorDistort = 0.75, mirrorLines = 560, mirrorCull = false, night = {}, seaVariation = null } = {}) {
  SEA_VAR = seaVariation ? { silt: 1, streaks: 1, windy: 1, gusts: 1, ...seaVariation } : null;
  REFL_LINES = mirrorLines;
  MIRROR_CULL = !!mirrorCull;
  NIGHT = { ...NIGHT, ...night };
  WIND = windAngle(windFrom);
  MIRROR_BLUR = mirrorBlur;
  reflDistort.value = mirrorDistort;
  MIRROR_Y = mirror;
  COLOURS = { sea: { ...COLOURS.sea, ...sea }, inland: { ...COLOURS.inland, ...inland },
    skySaturation: { ...COLOURS.skySaturation, ...skySaturation } };
  // two seas: long-crested (narrow spread) and choppy (wide spread), alternated between the scales
  const wavesA = waveTexture(20240526, 0.3);
  const wavesB = waveTexture(88172, 0.75);
  LAYERS = [
    { tex: wavesA, size: 197, turn: 0.0, w: 0.016, wind: 0.3, warp: 0 },
    { tex: wavesB, size: 53.3, turn: 0.61, w: 0.022, wind: 0.6, warp: 45 },
    { tex: wavesA, size: 14.1, turn: -0.43, w: 0.025, wind: 1, warp: 23 },
    { tex: wavesB, size: 3.37, turn: 0.97, w: 0.025, wind: 1, warp: 7 },
    { tex: wavesA, size: 0.91, turn: -1.21, w: 0.022, wind: 1, warp: 2 },
  ];
}

// (city.json water.seaVariation, opt-in; null: the shader unchanged) the sea's large-scale variation scaled towards its
// mean: silt plumes (9.3 km), wind streaks along the wind, the calm/windy patches (6.1 km) and each wave scale's gusts.
// Singapore M5: the open Strait read as marbled swirls over many km from the overview; its tint should vary only at
// the waves' scale
let SEA_VAR = null;
let NIGHT = { glow: 0.5, sky: 1, gain: 2, max: 2.5, streak: 3, knee: 0, base: 1 };
const RIPPLE_SIZE = 10;     // m: night.ripple's fine wave scales are those under this (3.4 and 0.9 m)
// Sky reflection strength. Physically 1, but the clear-sky model is far brighter near the sun and the
// horizon than the hazy delta sky, and without this the water turns white towards the light.
const reflectUniform = uniform(0.6);
// how far (in screen uv per unit of slope) the wave slopes shift and smear the mirrored city
const reflDistort = uniform(0.75);
// soft limit of the reflected sky luminance (see buildWater)
const skyLimit = uniform(1.6);
const reflHeight = uniform(1).onRenderUpdate(() => reflTarget.height);

function buildWater({ env, sea, fog, sunDir, night, edge: hazeEdge = null, haze = null }) {
  if (!LAYERS) configureWater();
  const C = COLOURS.sea, CI = COLOURS.inland, skySat = COLOURS.skySaturation;
  const mat = new THREE.MeshStandardNodeMaterial({ metalness: 0 });
  mat.userData.water = true;                         // left out of the reflection pass
  const P = positionWorld.xz;

  // shore distance: inside the extent from the field; outside it, the distance beyond the extent's edge,
  // so the sea past a cut-off coast still starts out coastal and clears offshore
  const suv = P.sub(shoreBox.xy).div(shoreBox.zw);
  const sdf = texture(shoreTex, suv);
  const outside = max(max(shoreBox.x.sub(P.x), P.x.sub(shoreBox.x.add(shoreBox.z))),
    max(shoreBox.y.sub(P.y), P.y.sub(shoreBox.y.add(shoreBox.w)))).max(0);
  const dNear = max(sdf.r.sub(0.5).mul(2 * SHORE_NEAR), outside.min(SHORE_NEAR));     // metres, +-300
  const dFar = max(sdf.g.mul(SHORE_FAR), outside);                                    // metres, 0..8000
  // 1 on the open sea and in the inland water that opens onto it, 0 on rivers and lakes further inland
  // (inland.seaLink false: no inland water takes the sea's look, for a city whose rivers leave the extent far from any
  // sea: London's Thames ran out of the ground area at both ends and was drawn as the open estuary, slate blue)
  const seaness = sea ? float(1) : CI.seaLink === false ? float(0)
    : attribute('waterKind', 'vec2').x.mul(float(1).sub(smoothstep(float(150), float(SEA_REACH * 0.9), sdf.a.mul(SEA_REACH))));

  // calm and windy patches, plus streaks drawn out along the wind the way slicks and wind lanes are
  // (darker, glassier streaks on every photo of the bay). The streaks' cross-wind coordinate is bent by
  // a slow noise so they meander instead of running as straight parallel lanes.
  const wc = Math.cos(WIND), ws = Math.sin(WIND);
  const p1 = texture(patches, P.div(6100).add(slickShift.xy));
  const bend = texture(patches, P.div(2700).add(vec2(0.31, 0.77)));
  const along = P.x.mul(wc).add(P.y.mul(ws)), across = P.y.mul(wc).sub(P.x.mul(ws)).add(bend.r.sub(0.5).mul(900));
  const p2 = texture(patches, vec2(along.div(3900).add(slickShift.z), across.div(520)));
  let windy = smoothstep(float(0.2), float(0.8), p1.r.mul(0.6).add(p2.b.mul(0.4)));
  if (SEA_VAR && SEA_VAR.windy !== 1) windy = mix(float(0.5), windy, float(SEA_VAR.windy));
  const calmShore = smoothstep(float(0), mix(float(40), float(120), seaness), dNear); // lee of seawalls, banks
  // fetch (open water upwind, see shoreField): harbour basins, marinas and coves behind breakwaters are
  // calm, their long waves never grow and they mirror the quays; beyond the extent it is open sea
  const fetchM = max(sdf.b.mul(FETCH_MAX), outside.mul(10)).min(FETCH_MAX);
  const exposure = mix(float(1), smoothstep(float(150), float(1800), fetchM), seaness);
  const windAmt = mix(float(0.35), float(1.2), windy).mul(mix(float(0.6), float(1), calmShore)).mul(mix(float(0.6), float(1), exposure));
  // inland water is sheltered, ponds stillest: all scales shrink there, the long ones as much as the short
  const ST = CI.still;
  const still = !sea && ST ? attribute('waterStill', 'float') : null;
  let shelter = sea ? float(1) : mix(float(CI.riverWaves), float(0.08), attribute('waterKind', 'vec2').y);
  if (still) shelter = mix(shelter, float(ST.waves ?? 0.06), still);
  if (!sea) shelter = mix(shelter, float(1), seaness);

  // slopes: sum of the layers; unresolved variance from the mipmapped squared slopes
  const warpN = texture(patches, P.div(900).add(vec2(0.53, 0.11))).rg.sub(0.5);
  // rivers and canals: the current carries the ripples downstream. Two copies of each scale, shifted by
  // the current over the two halves of a flow-map period and cross-faded (each weighs nothing at the
  // moment it jumps back), so the pattern flows without being stretched where the current varies.
  const flow = sea ? null : attribute('waterFlow', 'vec2');
  const fw0 = float(1).sub(flowPhase.x.mul(2).sub(1).abs()), fw1 = float(1).sub(fw0);
  const fnorm = fw0.mul(fw0).add(fw1.mul(fw1)).sqrt();              // keeps the blend's contrast
  let slope = vec2(0, 0), variance = float(0);
  // (night.ripple, below: the slope of the wave scales of RIPPLE_SIZE m and more alone)
  const RIPPLE = NIGHT.tapKnee && NIGHT.ripple != null;
  let slopeLo = vec2(0, 0), varFine = float(0);
  // (night.blur, with ripple, mip levels, default none: Tokyo tk3, the user 8 Oct: a fine grain still in the Sumida's mirror of the
  // lit towers beside Kachidoki from 40 m) the night's slopes read that many mip levels blurrier than the pixel's own, the
  // detail lost counted as roughness (the mips' mean squared slope). At the pixel's own level the 14 and 53 m scales far
  // off, a texel a pixel, still moved each pixel's lookup on its own: a grain of single pixels in every mirrored light.
  // A uniform (nightTaps.blur; 0: as ripple alone)
  const BLUR = RIPPLE && NIGHT.blur != null ? uniform(NIGHT.blur) : null;
  let slopeB = vec2(0, 0), slopeLoB = vec2(0, 0), varB = float(0);
  LAYERS.forEach((L, i) => {
    const c = Math.cos(L.turn), s = Math.sin(L.turn);
    const Q = P.add(warpN.mul(L.warp));
    const layer = (Qk, bias = null) => {
      const uvL = vec2(Qk.x.mul(c).sub(Qk.y.mul(s)), Qk.x.mul(s).add(Qk.y.mul(c))).div(L.size).add(layerShift[i]);
      const t = bias ? texture(L.tex.tex, uvL).bias(bias) : texture(L.tex.tex, uvL);
      const m = t.rg.mul(2).sub(1).mul(L.tex.S);                     // mean slope over the pixel (texture axes)
      const e2 = t.b.add(t.a).mul(L.tex.S * L.tex.S);                // mean squared slope, both axes
      return { m, v: max(e2.sub(m.dot(m)), 0) };
    };
    const read = (bias = null) => {
      if (sea) return layer(Q, bias);
      const a = layer(Q.sub(flow.mul(flowPhase.x.sub(0.5).mul(FLOW_PERIOD))), bias);
      const b = layer(Q.sub(flow.mul(flowPhase.y.sub(0.5).mul(FLOW_PERIOD))), bias);
      return { m: a.m.mul(fw0).add(b.m.mul(fw1)).div(fnorm), v: a.v.mul(fw0).add(b.v.mul(fw1)) };
    };
    const { m, v } = read();
    // each scale's own slow swell of strength, from one patch channel at its own scale (gusts)
    const amp = texture(patches, P.div(L.size * 17 + 400).add(vec2(0.17 * i, 0.29 * i)).add(gustShift[i]))[['r', 'g', 'b'][i % 3]]
      .mul(1.1).add(0.45);
    const ampV = SEA_VAR && SEA_VAR.gusts !== 1 ? mix(float(1), amp, float(SEA_VAR.gusts)) : amp;
    // a wave scale needs a fetch of some 25 of its tiles to grow fully (sea and river mouths only)
    const grown = mix(float(1), fetchM.div(L.size * 25).sqrt().clamp(0.15, 1), seaness);
    const w = mix(float(1), windAmt, L.wind).mul(shelter).mul(ampV).mul(grown).mul(L.w);
    // back to world axes (rotate by -turn)
    const mw = vec2(m.x.mul(c).add(m.y.mul(s)), m.y.mul(c).sub(m.x.mul(s))).mul(w);
    slope = slope.add(mw);
    variance = variance.add(v.mul(w.mul(w)).mul(0.5));
    if (BLUR) {
      const b = read(BLUR);
      const mwB = vec2(b.m.x.mul(c).add(b.m.y.mul(s)), b.m.y.mul(c).sub(b.m.x.mul(s))).mul(w);
      slopeB = slopeB.add(mwB);
      if (L.size >= RIPPLE_SIZE) slopeLoB = slopeLoB.add(mwB);
      varB = varB.add(b.v.mul(w.mul(w)).mul(0.5));
    }
    if (RIPPLE) {
      if (L.size >= RIPPLE_SIZE) slopeLo = slopeLo.add(mw);
      // (its expected variance, w^2 (rms per axis w), not the pixel's own resolved slope squared: that varied from
      // pixel to pixel as much as the slope itself and made each pixel's streak length and blur its own)
      else varFine = varFine.add(w.mul(w));
    }
  });
  // geometric anti-aliasing: slope change across one pixel is unresolved too
  const dS = fwidth(slope);
  // (night.ripple: the variance without the fine ripples' pixel-to-pixel change, which is as noisy as they are)
  const dSLo = RIPPLE ? fwidth(BLUR ? slopeLoB : slopeLo) : null;
  const varianceLo = RIPPLE ? (BLUR ? varB : variance).add(dSLo.dot(dSLo).mul(0.25)) : null;
  // (night.blur: the blurred slopes stand in for the pixel's own in the night's surface below)
  if (BLUR) { slopeLo = slopeLoB; }
  variance = variance.add(dS.dot(dS).mul(0.25));
  const nWorld = vec3(slope.x.negate(), 1, slope.y.negate()).normalize();
  mat.normalNode = cameraViewMatrix.mul(vec4(nWorld, 0)).xyz.normalize();
  // Beckmann/GGX: alpha^2 ~ 2 sigma^2; three's roughness is sqrt(alpha). Resolved facets stay glassy
  // (alpha 0.02), so the glitter near the camera breaks into sparkles.
  const alpha = sqrt(variance.mul(2).add(0.0004));
  const rough = sqrt(alpha).clamp(0.08, 0.7);
  mat.roughnessNode = rough;

  // Fresnel (water F0 = 0.02). Unresolved waves matter most at grazing views: the facets we see there
  // lean towards us, so they meet the eye less obliquely (less Fresnel) and mirror higher, darker sky
  // than a flat surface would.
  const sigma = sqrt(variance.mul(2));
  const V = cameraPosition.sub(positionWorld).normalize();
  const ndv = max(nWorld.dot(V), sigma.mul(0.9)).clamp(0.0, 1);
  const fresnel = float(0.02).add(float(0.98).mul(pow(float(1).sub(ndv), 5)));

  // body colour: what the silt and plankton scatter back up (linear albedo, lit by sun and sky)
  const p3 = texture(patches, P.div(9300).add(vec2(0.37, 0.61)));
  // the sea (by default the estuary: silty grey green-brown, lighter along the shore, bluer offshore), with
  // plumes and streaks
  const silt = smoothstep(float(0.3), float(0.8), p3.g);            // plumes of muddier water
  const shoreBrown = vec3(...C.shore);                               // silty band along the coast
  const nearGreen = vec3(...C.near);                                 // bay water
  const offshore = vec3(...C.offshore);                              // open estuary: grey-blue
  let seaBody = mix(nearGreen, offshore, smoothstep(float(600), float(6500), dFar));
  seaBody = mix(seaBody, vec3(...C.silt), silt.mul(0.55 * (SEA_VAR?.silt ?? 1)).mul(float(1).sub(smoothstep(float(3000), float(9000), dFar))));
  seaBody = mix(shoreBrown, seaBody, smoothstep(float(10), float(180), dNear));
  // enclosed basins: deeper, dredged and stirred less, so darker and greener than the silty bay
  seaBody = mix(seaBody, vec3(...C.basin), float(1).sub(exposure).mul(0.65));
  seaBody = seaBody.mul(p2.g.sub(0.5).mul(0.16 * (SEA_VAR?.streaks ?? 1)).add(1));            // turbidity streaks along the wind
  let body = seaBody;
  if (!sea) {
    // rivers are all "near the bank", murky green-brown; ponds and reservoirs are stiller, deeper and
    // darker, olive to bottle green (algae), with patches of greener water
    const river = vec3(...CI.river);
    const lake = vec3(...CI.lake);
    let inland = mix(river, lake, attribute('waterKind', 'vec2').y);
    // fountain basins and garden pools (inland.basin; null: like any pond): shallow water over a pale floor, so
    // lighter than a lake, never the black of a deep pond seen from above
    // still water (inland.still): impounded docks and park lakes, slate grey-green, under the basins' pale floor
    if (still) inland = mix(inland, vec3(...ST.body), still);
    if (CI.basin) inland = mix(inland, vec3(...CI.basin), attribute('waterBasin', 'float'));
    const algae = texture(patches, P.div(310).add(vec2(0.71, 0.23)));
    inland = mix(inland, inland.mul(vec3(0.95, 1.3, 1.0)), smoothstep(float(0.45), float(0.85), algae.b).mul(0.8));
    inland = inland.mul(p3.g.sub(0.5).mul(0.3).add(1));
    body = mix(inland, seaBody, seaness);
  }
  // Light leaving the water body is lit like a flat surface whatever the waves do (it comes from inside);
  // three lights the albedo with the wave normal, so undo the sun's share of that (n.l over flat n.l),
  // or the body colour itself would ripple like crumpled foil. Only what the surface lets through
  // (1 - Fresnel) comes back out.
  // a live uniform on the viewer's sun direction, so the time-of-day setting relights the water
  const sun = uniform(sunDir);
  const flatten = sun.y.div(max(nWorld.dot(sun), 0.05)).clamp(0.5, 2);
  // (inland.riverReflect, still.reflect: a turbid river keeps less of the reflection than Fresnel says, its body
  // colour showing through instead, even at grazing angles; still water mirrors fully)
  let reflK = sea ? float(1) : mix(float(CI.riverReflect), float(1), seaness);
  // (inland.reflectGrazing, default none: the share at grazing views, riverReflect's from ~35 degrees down: a
  // turbid river seen from above shows its silt, seen along its length it mirrors the sky like any water; London
  // M7 fix round: riverReflect alone left the Thames an opaque olive band at the overview and the estuary)
  if (!sea && CI.reflectGrazing != null) reflK = mix(float(CI.reflectGrazing), reflK, smoothstep(float(0.08), float(0.55), ndv));
  if (still) reflK = mix(reflK, float(ST.reflect ?? 1), still);
  // (at most the whole reflection: still.reflect over 1 lifts calm water's sky at steep views, but at grazing ones it
  // pushed the reflection past the sky itself and the body below black: London M7, a paddling pool on Parliament
  // Hill's slope a flat near-white sheet)
  const fresnelK = fresnel.mul(reflK).min(1);
  mat.colorNode = body.mul(float(1).sub(fresnelK)).mul(flatten);

  // sky reflection from the PMREM; below the horizon (steep wave facets at grazing views) it shows the
  // hazy dark foot of the sky instead
  // (a function: night.blur takes the night's sky the same way off its smoothed surface)
  const reflDir = (n, sg) => {
    const R0 = V.negate().reflect(n).normalize();
    return vec3(R0.x, R0.y.add(sg.mul(0.7)), R0.z).normalize();
  };
  const R = reflDir(nWorld, sigma);
  const skyOf = (R, rough) => {
  const skyR = pmremTexture(env, vec3(R.x, R.y.max(0.02), R.z), rough.mul(0.8)).rgb;
  const horizon = pmremTexture(env, vec3(R.x, float(0.03), R.z), float(0.4)).rgb;
  const below = smoothstep(float(0.02), float(-0.08), R.y);
  let sky = mix(skyR, horizon.mul(vec3(0.34, 0.34, 0.32)), below);
  // a humid sky (such as the Pearl River delta's) is paler than the clear-sky model: take some colour out
  // (more so on still inland water, which mirrors the deep blue overhead rather than the hazy low sky)
  sky = mix(vec3(sky.dot(vec3(0.2126, 0.7152, 0.0722))), sky, mix(float(skySat.inland), float(skySat.sea), seaness));
  // The haze round the sun (Mie glow) is several times brighter than the rest of the sky, and blurred by
  // rough water it would spread into a sheet of white foil over everything looking sunwards. The glint
  // itself is the sun light's specular; the glow's share in the reflection is compressed softly towards
  // the brightness of the horizon haze (about the fog colour, ~1.2).
  const skyL = sky.dot(vec3(0.2126, 0.7152, 0.0722));
  sky = sky.div(skyL.div(skyLimit).add(1)).mul(skyLimit.add(1).div(skyLimit));
  // wind-roughened patches catch more of the bright low sky than the glassy slicks between them
  // (calm inland water mirrors the mid sky, never the glare near the horizon: a stronger share)
  sky = sky.mul(reflectUniform).mul(mix(float(0.8), float(1.15), windy)).mul(mix(float(1.2), float(1), seaness));
  // turbid inland water (the Seine's green-brown): the mirrored sky takes on a little of the water's own tint
  // (inland.skyTint; null: none)
  if (!sea && CI.skyTint) sky = sky.mul(mix(vec3(...CI.skyTint), vec3(1, 1, 1), seaness));
  return sky;
  };
  const sky = skyOf(R, rough);

  // the mirrored city (renderWaterReflection): looked up where this pixel is on screen, shifted by the
  // resolved wave slopes as seen on screen, and smeared vertically by the unresolved ones (reflections
  // on rippled water stretch into streaks towards the viewer), with blurrier mip levels as it roughens
  const tilt = cameraViewMatrix.mul(vec4(nWorld.x, 0, nWorld.z, 0)).xy;
  const uvS = screenUV.add(vec2(tilt.x.negate(), tilt.y).mul(reflDistort).clamp(-0.2, 0.2));
  // screen uv -> the target, which covers reflRect mirrored left-right
  const uvR = vec2(reflRect.x.add(reflRect.z).sub(uvS.x).div(reflRect.z), uvS.y.sub(reflRect.y).div(reflRect.w));
  const smear = sigma.mul(reflDistort).mul(1.6).add(0.002).div(reflRect.w);        // in target uv
  // (at least a level 1.4 blur: the slope-shifted lookups of the half-size target read as stair-stepped shards
  // on Paris's calm river, M5 critic)
  const lvl = smear.mul(reflHeight).mul(0.35).max(2 ** Math.max(MIRROR_BLUR, 0)).log2();
  // after dark (night.js's lights) the mirrored lights stretch into longer streaks down the ripples (the
  // taps spread further, the blur stays), and read brighter: bright windows and lamps are what the smear
  // of a night mirror is made of
  const nightK = night ? night.lights : float(0);
  const streak = smear.mul(nightK.add(1));
  let mirrored = vec4(0, 0, 0, 0);
  // (the taps staggered sideways by a little under a texel of the target, so they filter across as well)
  const side = float(MIRROR_BLUR ? 0.7 : 0).div(reflHeight.mul(reflRect.z.div(reflRect.w)).max(1));
  for (const [k, j] of [[-0.75, -1], [-0.25, 1], [0.25, -1], [0.75, 1]]) {
    mirrored = mirrored.add(texture(reflTarget.texture, uvR.add(vec2(side.mul(j), streak.mul(k)))).level(lvl).mul(0.25));
  }
  // only inside the part of the view the target covers (far hazy water may lie outside it)
  const edge = (t, lo, hi) => smoothstep(lo, lo.add(0.01), t).mul(float(1).sub(smoothstep(hi.sub(0.01), hi, t)));
  // The mirror is the plane y = MIRROR_Y; water well above it (reservoirs up in the hills, such as
  // Shenzhen's 西丽, 铁岗, 石岩) would show the city displaced by twice its height, so there it fades out
  // and the low sky it would have shown gives way to the dark wooded banks such a lake mirrors instead
  const onPlane = float(1).sub(smoothstep(float(3), float(8), abs(positionWorld.y.sub(MIRROR_Y))));
  const inRect = edge(uvS.x, reflFade.x, reflFade.z).mul(edge(uvS.y, reflFade.y, reflFade.w)).mul(reflOn).mul(onPlane);
  const cover = mirrored.a.mul(inRect).clamp(0, 1);
  // (not over fountain basins: they lie in open squares and gardens, under open sky)
  const basinK = !sea && CI.basin ? float(1).sub(attribute('waterBasin', 'float')) : float(1);
  let banks = float(1).sub(onPlane).mul(smoothstep(float(0.3), float(0.04), R.y)).mul(basinK);
  if (still) banks = banks.mul(mix(float(1), float(ST.banks ?? 1), still));
  // premultiplied: the target was cleared to transparent black
  const reflected = mix(sky, vec3(0.035, 0.05, 0.04), banks.mul(0.85)).mul(float(1).sub(cover)).add(mirrored.rgb.mul(inRect).mul(nightK.mul(0.6).add(1)));

  mat.emissiveNode = reflected.mul(fresnelK);
  // After dark (the material's lit copy, night.js: by day nothing of this is drawn) the mirrored lights run into
  // long streaks down the ripples: eight taps over a streak a few per cent of the view high, weighted towards its
  // middle, and read brighter than the Fresnel alone would let them (a lamp is thousands of times brighter than
  // the dark water; in a tone-mapped frame they would vanish); the water never quite black: the city's glow on
  // the haze mirrored in it
  let nightEmissive = null, litSurface = () => {};
  if (night) {
    // (night.tapKnee, Tokyo M8 fix round 2, default off: the knee taken off each of the streak's taps before they are
    // averaged, not off their average: a lit window or lamp is one tap in eight, so a longer streak averaged it under
    // the knee and the streaks vanished as they were lengthened (Tokyo M8: streak 8 with knee 0.15 left the bay and
    // the Sumida flat navy under rows of lit towers); peak: that share of the brightest tap instead of the mean, the
    // streak as bright all down its length; fres: the least Fresnel share the lights keep (default 0.06, as the rest),
    // a lamp outshining the dark water looking down on it as well as along it (with the knee higher, the far river's
    // lit-window sheet stays out while the near water under the towers streaks). Its settings are uniforms (mat.userData.nightTaps), for the console;
    // on = 0 there: the knee off the mean again, for an A/B in the page)
    const TK = NIGHT.tapKnee ? { knee: uniform(NIGHT.knee), gain: uniform(NIGHT.gain), max: uniform(NIGHT.max),
      streak: uniform(NIGHT.streak), peak: uniform(NIGHT.peak ?? 0), fres: uniform(NIGHT.fres ?? 0.06), on: uniform(1),
      ripple: uniform(NIGHT.ripple ?? 1), ...(BLUR ? { blur: BLUR, soft: uniform(NIGHT.soft ?? 0), tilt: uniform(NIGHT.tilt ?? 1) } : {}) } : null;
    // (night.steep { knee, gain, at: [lo, hi] }, Hong Kong M8 fix round 1, default none: looking down on the water (the
    // camera from lo to hi m up; the mirror's camera as far below) the knee and gain become these: from the Peak the mirrored lit districts, boosted
    // whole, spread into an amber sheet; from the shore the same settings give the streaks)
    const ST = NIGHT.steep, steepT = ST ? smoothstep(float(ST.at?.[0] ?? 150), float(ST.at?.[1] ?? 500), abs(cameraPosition.y)) : null;
    const knee0 = TK ? TK.knee : NIGHT.knee, gain0 = TK ? TK.gain : NIGHT.gain;
    // (with tapKnee the uniforms on both sides, so nightTaps.knee and .gain reach a view under steep.at too; same values)
    const kneeN = ST ? mix(TK ? knee0 : float(NIGHT.knee), ST.knee != null ? float(ST.knee) : knee0, steepT) : knee0;
    const gainN = ST ? mix(TK ? gain0 : float(NIGHT.gain), ST.gain != null ? float(ST.gain) : gain0, steepT) : gain0;
    // (with tapKnee, steep.peak and steep.fres (Tokyo, 8 Oct, the user: the Sumida from the air "a dense field of white dots,
    // like static"): looking down, the brightest tap's share and the Fresnel floor become these. From above the mirror
    // shows the far bank's lit walls whole; the floor (0.2 against a Fresnel of ~0.03 there) and the gain made every
    // lit window in it a white dot, broken up pixel by pixel by the ripples' slopes; with the plain Fresnel and the
    // taps' mean the river reads dark, its lights soft streaks)
    const peakN = TK && ST?.peak != null ? mix(TK.peak, float(ST.peak), steepT) : TK?.peak;
    const fresN = TK && ST?.fres != null ? mix(TK.fres, float(ST.fres), steepT) : TK?.fres;
    const streakN = TK ? smear.mul(TK.streak).add(TK.streak.mul(0.01).div(reflRect.w))
      : smear.mul(NIGHT.streak).add(float(0.01 * NIGHT.streak).div(reflRect.w));
    // (night.ripple, with tapKnee, 0..1, default none: Tokyo tk2, the user 8 Oct: the Sumida "static-like sparkle" at every
    // height, a bright white noisy sheet beside Kachidoki from 40 m) after dark the mirrored lights are looked up, and
    // their Fresnel taken, with only that share of the fine ripples' (the 3.4 and 0.9 m scales') slopes; the rest
    // counts as roughness (its slope variance), which lengthens and blurs the streaks instead. Resolved a few pixels
    // across, those ripples moved each pixel's lookup and Fresnel on their own (at grazing views the Fresnel of a
    // lit window's mirror jumped 0.05-0.5 from pixel to pixel): with the gain that a lamp's streak needs, a field of
    // white dots. The day's mirror is unchanged.
    let uvRN = uvR, lvlN = lvl, fresnelL = fresnel, streakL = streakN, litNormal = null, litRough = null;
    let skyNight = sky, litColor = null, floorK = fresnel;
    if (RIPPLE) {
      const slopeN = BLUR ? slopeLo.add(slopeB.sub(slopeLo).mul(TK.ripple)) : slopeLo.add(slope.sub(slopeLo).mul(TK.ripple));
      const nN = vec3(slopeN.x.negate(), 1, slopeN.y.negate()).normalize();
      const sigmaN = sqrt(mix(variance, varianceLo.add(varFine), float(1).sub(TK.ripple.mul(TK.ripple))).mul(2));
      const ndvN = max(nN.dot(V), sigmaN.mul(0.9)).clamp(0.0, 1);
      fresnelL = float(0.02).add(float(0.98).mul(pow(float(1).sub(ndvN), 5)));
      const tiltN = cameraViewMatrix.mul(vec4(nN.x, 0, nN.z, 0)).xy;
      // (night.tilt, with blur, default 1: the waves' shift of the night's lookup that much; under 1 the long swells no longer
      // carry a far bank's row of lit windows up and down the river in horizontal blotches, and the streaks run straight)
      const uvSN = screenUV.add(vec2(tiltN.x.negate(), tiltN.y).mul(BLUR ? reflDistort.mul(TK.tilt) : reflDistort).clamp(-0.2, 0.2));
      uvRN = vec2(reflRect.x.add(reflRect.z).sub(uvSN.x).div(reflRect.z), uvSN.y.sub(reflRect.y).div(reflRect.w));
      const smearN = sigmaN.mul(reflDistort).mul(1.6).add(0.002).div(reflRect.w);
      lvlN = smearN.mul(reflHeight).mul(0.35).max(2 ** Math.max(MIRROR_BLUR, 0)).log2();
      // (night.soft, with blur, mip levels, default 0: the mirror that much blurrier after dark, the lit banks and towers
      // soft smears rather than their windows' and bands' sharp copies bent by the waves; a uniform, nightTaps.soft)
      if (BLUR) lvlN = lvlN.add(TK.soft);
      streakL = smearN.mul(TK.streak).add(TK.streak.mul(0.01).div(reflRect.w));
      // (the moon's and the lamps' own glints on the same smoothed surface: on the resolved ripples they were a glitter of
      // single pixels over the half of the river towards the moon)
      litNormal = cameraViewMatrix.mul(vec4(nN, 0)).xyz.normalize();
      litRough = sqrt(sqrt(sigmaN.mul(sigmaN).add(0.0004))).clamp(0.08, 0.7);
      if (BLUR) {
        // (night.blur: the mirrored night sky, the body's share and the floor off the same smoothed surface: the sky's lookup,
        // its horizon cut and the body's Fresnel and sun share on the pixel's own normal were a grain of their own)
        skyNight = skyOf(reflDir(nN, sigmaN), litRough);
        const flattenN = sun.y.div(max(nN.dot(sun), 0.05)).clamp(0.5, 2);
        litColor = body.mul(float(1).sub(fresnelL.mul(reflK).min(1))).mul(flattenN);
        floorK = fresnelL;
      }
    }
    let mirN = vec4(0, 0, 0, 0), wsum = 0, litN = vec3(0, 0, 0), litPeak = vec3(0, 0, 0);
    for (let i = 0; i < 8; i++) {
      const k = (i + 0.5) / 8 * 2 - 1, w = 1 - Math.abs(k) * 0.7;
      wsum += w;
      const tap = texture(reflTarget.texture, uvRN.add(vec2(side.mul(i % 2 ? 1 : -1), streakL.mul(k)))).level(lvlN);
      mirN = mirN.add(tap.mul(w));
      if (TK) {
        // (on the tap's luminance, its colour kept: a knee on each channel left the warm windows' red alone over it,
        // and the Sumida's streaks read pink-red)
        const lum = tap.rgb.dot(vec3(0.2126, 0.7152, 0.0722));
        const over = tap.rgb.mul(max(lum.sub(kneeN), 0).div(max(lum, 1e-4)));
        litN = litN.add(over.mul(w));
        litPeak = max(litPeak, over);
      }
    }
    mirN = mirN.div(wsum);
    if (TK) litN = mix(litN.div(wsum), litPeak, peakN);
    const coverN = mirN.a.mul(inRect).clamp(0, 1);
    // (sky and base: the night's shares, reached as the twilight gives way to the city's glow (cityGlow): at dusk
    // the water still mirrors the bright sky and the city as it is)
    const baseK = mix(float(1), float(NIGHT.base), night.cityGlow.pow(3));
    // (night.zenith, Hong Kong M8 fix round 1, default none: that share of the mirrored night sky is the navy zenith's colour
    // (night.js) instead of the rough water's blur of the low sky, whose city glow made the harbour an amber sheet from the
    // Peak; reached as the city's glow takes over)
    const skyN0 = NIGHT.sky === 1 ? skyNight : skyNight.mul(mix(float(1), float(NIGHT.sky), night.cityGlow.pow(3)));
    const skyN = NIGHT.zenith != null ? mix(skyN0, night.zenith.mul(reflectUniform), night.cityGlow.pow(3).mul(NIGHT.zenith)) : skyN0;
    // (night.desatLights, 0..1, default none (Hong Kong M8 critic 2): the boosted lights over the knee that share towards their
    // luminance too: from above, the red signs' mirrored glow spread into rust-red smears on the harbour)
    const boostN = (c) => NIGHT.desatLights ? mix(c, vec3(c.x.mul(0.2126).add(c.y.mul(0.7152)).add(c.z.mul(0.0722))), float(NIGHT.desatLights)) : c;
    const frN = fresnelL;      // (night.ripple: the smoothed Fresnel throughout; else the Fresnel)
    const reflN = mix(skyN, vec3(0.035, 0.05, 0.04), banks.mul(0.85)).mul(float(1).sub(coverN)).mul(frN)
      .add((NIGHT.knee || NIGHT.base !== 1
        // (desat, desatTint: the kept rest (base) that share greyer, towards its luminance times the tint: the mirrored haze
        // over the horizon read as a wine-red sheet up the Spree, Berlin M8 fix round)
        // (knee: only what is brighter than it, the lights, is boosted; base: the share of the rest, the mirrored
        // haze and dark city, kept: with the whole mirror boosted the lit haze over the horizon made the river a
        // brown sheet, London M8)
        ? (NIGHT.desat ? mix(mirN.rgb, vec3(mirN.rgb.x.mul(0.2126).add(mirN.rgb.y.mul(0.7152)).add(mirN.rgb.z.mul(0.0722))).mul(vec3(...(NIGHT.desatTint ?? [1, 1, 1]))), float(NIGHT.desat)) : mirN.rgb).mul(baseK).add(boostN(TK ? mix(max(mirN.rgb.sub(kneeN), vec3(0, 0, 0)), litN.mul(max(fresnelL, fresN).div(max(frN, 0.06))), TK.on) : max(mirN.rgb.sub(kneeN), vec3(0, 0, 0))).mul(float(1).sub(frN).mul(night.lights).mul(gainN).add(float(1).sub(baseK))))
        : mirN.rgb.mul(float(1).sub(frN).mul(night.lights).mul(NIGHT.gain).add(1)))
        .mul(inRect).mul(max(frN, 0.06)).min(TK ? TK.max : NIGHT.max));
    nightEmissive = reflN.add(night.skyGlow.mul(NIGHT.glow));
    if (TK) mat.userData.nightTaps = TK;
    // (night.floor [r, g, b], linear: the least the water shows after dark, the navy sky's sheen on it; London M8 fix
    // round: between the streaks the Thames read as a black void)
    if (NIGHT.floor) nightEmissive = nightEmissive.add(vec3(...NIGHT.floor).mul(night.lights).mul(floorK.mul(0.5).add(0.5)));
    litSurface = (lit) => {
      if (litNormal) { lit.normalNode = litNormal; lit.roughnessNode = litRough; }
      if (litColor) lit.colorNode = litColor;
    };
    if (!(sea && fog)) night.withNight(mat, (lit) => { lit.emissiveNode = nightEmissive; litSurface(lit); });
  }
  // intermediate nodes and the reflection strength, for trying things out from the browser console
  mat.userData.nodes = { dNear, dFar, seaness, windy, rough, body, fresnel, slope, reflected, cover, mirrored };
  mat.userData.reflect = reflectUniform;
  mat.userData.distort = reflDistort;
  mat.userData.skyLimit = skyLimit;
  mat.userData.reflTarget = reflTarget;
  mat.userData.reflRect = reflRect;

  // haze: the scene's FogExp2 (same colour, density and view-depth formula as three's), except that the
  // sea near the horizon, beyond the land, fades into the sky there instead of the flat fog colour, so
  // the 400 km quad meets the sky without a seam
  if (sea && fog) {
    mat.fog = false;
    const density = uniform(fog.density).onRenderUpdate(() => fog.density);
    const fogColor = uniform(fog.color);
    const viewZ = positionView.z.negate();
    let amount = float(1).sub(density.mul(density).mul(viewZ).mul(viewZ).negate().exp());
    // (city.json haze.edge: beyond the backdrop's fade the sea is haze too, as the land is (main.js), so the quad
    // past the backdrop's edge shows no band of water between the faded land and the sky)
    if (hazeEdge) amount = amount.max(smoothstep(float(hazeEdge[0]), float(hazeEdge[1]), positionWorld.xz.length()));
    const look = positionWorld.sub(cameraPosition).normalize();
    const skyHorizon = pmremTexture(env, vec3(look.x, 0.01, look.z).normalize(), float(0.05)).rgb;
    const toSky = smoothstep(float(20000), float(70000), viewZ).mul(smoothstep(float(0.12), float(0.03), look.y.negate()));
    // (main.js's haze by height, city.json haze.height: by day the land's own haze, vec4(colour, amount), which
    // already fades into the sky over the horizon)
    mat.outputNode = haze ? vec4(mix(output.rgb, haze.rgb, haze.a), output.a)
      : vec4(mix(output.rgb, mix(fogColor, skyHorizon, toSky), amount), output.a);
    // after dark the haze lit by the city too (night.js), as main.js's night fog adds it to the land's, in
    // the sea's lit copy (per pixel: the sea is one huge quad; drawn first as a depthless backdrop, as
    // main.js draws the sea)
    if (night) {
      mat.depthWrite = false;
      night.withNight(mat, (lit) => {
        lit.emissiveNode = nightEmissive;
        litSurface(lit);
        const depth = density.mul(density).mul(viewZ).mul(viewZ).add(night.hazeDepth(viewZ));
        let nightAmount = float(1).sub(depth.negate().exp());
        if (hazeEdge) nightAmount = nightAmount.max(smoothstep(float(hazeEdge[0]), float(hazeEdge[1]), positionWorld.xz.length()));
        lit.outputNode = vec4(mix(output.rgb, mix(fogColor, skyHorizon, toSky), nightAmount), output.a);
      });
    }
  }
  return mat;
}

// env: the sky PMREM from main.js
// fog: the scene's FogExp2, which the sea applies itself (see above)
// sunDir: unit vector towards the sun (the body colour is lit as flat water, see above)
// night: the uniforms from night.js (createNight().u), or null
const DEFAULT_SUN = new THREE.Vector3(-0.6, 0.53, 0.6).normalize();
export const createSeaMaterial = (env, fog, { sunDir = DEFAULT_SUN, night = null, edge = null, haze = null } = {}) => buildWater({ env, sea: true, fog, sunDir, night, edge, haze });
export const createInlandWaterMaterial = (env, { sunDir = DEFAULT_SUN, night = null } = {}) => buildWater({ env, sea: false, sunDir, night });
