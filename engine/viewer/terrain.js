// The ground's height anywhere in the scene: 05a_terrain.py's TIN (tiles/terrain.glb, written by 06_tiles.py),
// the very surface the ground layers, roads, buildings, markings and cars were laid on, so whatever the viewer
// places itself (trees scattered over their class raster, the orbit target, the camera) sits on the same
// ground. Linear on each triangle; 0 beyond the TIN (the sea, and the backdrop's hills, which nothing
// stands on).
//
// Point location: a bucket grid of BUCKET m cells listing the triangles that reach into each, built once
// when the TIN loads (some 100 ms for its ~600k triangles); a lookup tests the last triangle hit first,
// then its cell's few triangles, so a tree tile's tens of thousands of lookups take a few milliseconds.
import * as THREE from 'three/webgpu';

const BUCKET = 160;           // metres

export async function loadTerrain(loader, url) {
  const gltf = await loader.loadAsync(url);
  let mesh = null;
  gltf.scene.traverse((o) => { if (o.isMesh) mesh = o; });
  gltf.scene.updateMatrixWorld(true);
  const g = mesh.geometry, pos = g.attributes.position, e = mesh.matrixWorld.elements;
  const n = pos.count;
  const X = new Float64Array(n), Y = new Float64Array(n), Z = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    // quantized: grid index and height step, undone by the node's (axis-aligned) scale and translation
    X[i] = pos.getX(i) * e[0] + e[12];
    Y[i] = pos.getY(i) * e[5] + e[13];
    Z[i] = pos.getZ(i) * e[10] + e[14];
  }
  const idx = g.index.array, T = idx.length / 3;
  let x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
  for (let i = 0; i < n; i++) {
    x0 = Math.min(x0, X[i]); x1 = Math.max(x1, X[i]); z0 = Math.min(z0, Z[i]); z1 = Math.max(z1, Z[i]);
  }
  const nbx = Math.ceil((x1 - x0) / BUCKET) + 1, nbz = Math.ceil((z1 - z0) / BUCKET) + 1;
  // per triangle: corner a, and the inverse of the 2 x 2 matrix [b - a, c - a], for barycentric weights
  const A = new Float64Array(T * 8);
  const cellRange = new Int32Array(T * 4);
  const count = new Int32Array(nbx * nbz + 1);
  for (let t = 0; t < T; t++) {
    const a = idx[3 * t], b = idx[3 * t + 1], c = idx[3 * t + 2];
    const ux = X[b] - X[a], uz = Z[b] - Z[a], vx = X[c] - X[a], vz = Z[c] - Z[a];
    const det = ux * vz - vx * uz;
    A.set([X[a], Z[a], vz / det, -vx / det, -uz / det, ux / det, Y[b] - Y[a], Y[c] - Y[a]], t * 8);
    const i0 = Math.floor((Math.min(X[a], X[b], X[c]) - x0) / BUCKET), i1 = Math.floor((Math.max(X[a], X[b], X[c]) - x0) / BUCKET);
    const j0 = Math.floor((Math.min(Z[a], Z[b], Z[c]) - z0) / BUCKET), j1 = Math.floor((Math.max(Z[a], Z[b], Z[c]) - z0) / BUCKET);
    cellRange.set([i0, i1, j0, j1], t * 4);
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) count[j * nbx + i + 1]++;
  }
  for (let k = 1; k <= nbx * nbz; k++) count[k] += count[k - 1];
  const list = new Int32Array(count[nbx * nbz]);
  const fillAt = count.slice(0, nbx * nbz);
  for (let t = 0; t < T; t++) {
    const [i0, i1, j0, j1] = cellRange.subarray(t * 4, t * 4 + 4);
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) list[fillAt[j * nbx + i]++] = t;
  }
  const baseY = new Float64Array(T);
  for (let t = 0; t < T; t++) baseY[t] = Y[idx[3 * t]];

  let last = 0;
  // height of triangle t at (x, z), or NaN if (x, z) lies outside it (a hair of slack on its edges)
  const inTri = (t, x, z) => {
    const o = t * 8, dx = x - A[o], dz = z - A[o + 1];
    const u = A[o + 2] * dx + A[o + 3] * dz, v = A[o + 4] * dx + A[o + 5] * dz;
    if (u < -1e-7 || v < -1e-7 || u + v > 1 + 1e-7) return NaN;
    return baseY[t] + u * A[o + 6] + v * A[o + 7];
  };
  function height(x, z) {
    let y = inTri(last, x, z);
    if (y === y) return y;
    const i = Math.floor((x - x0) / BUCKET), j = Math.floor((z - z0) / BUCKET);
    if (i < 0 || j < 0 || i >= nbx || j >= nbz) return 0;
    const k = j * nbx + i;
    for (let p = count[k]; p < count[k + 1]; p++) {
      y = inTri(list[p], x, z);
      if (y === y) { last = list[p]; return y; }
    }
    return 0;
  }
  // the highest ground within r metres of (x, z) (its cell's triangles' corners and the point itself): a
  // cheap bound for keeping the camera out of the hills
  function ceiling(x, z, r) {
    let top = height(x, z);
    const i0 = Math.max(0, Math.floor((x - r - x0) / BUCKET)), i1 = Math.min(nbx - 1, Math.floor((x + r - x0) / BUCKET));
    const j0 = Math.max(0, Math.floor((z - r - z0) / BUCKET)), j1 = Math.min(nbz - 1, Math.floor((z + r - z0) / BUCKET));
    for (let j = j0; j <= j1; j++) {
      for (let i = i0; i <= i1; i++) {
        const k = j * nbx + i;
        for (let p = count[k]; p < count[k + 1]; p++) {
          const t = list[p];
          for (let c = 0; c < 3; c++) {
            const v = idx[3 * t + c];
            if (Math.abs(X[v] - x) <= r && Math.abs(Z[v] - z) <= r) top = Math.max(top, Y[v]);
          }
        }
      }
    }
    return top;
  }
  return { height, ceiling, box: new THREE.Box3(new THREE.Vector3(x0, 0, z0), new THREE.Vector3(x1, 0, z1)), triangles: T };
}
