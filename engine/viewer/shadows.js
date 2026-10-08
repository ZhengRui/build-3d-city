// Lighter sun shadow passes (city.json shadows; every option off by default, as New York and Shenzhen were measured).
// Two cuts, both meant to leave the shadows seen on screen as they were:
//
// groundSteep (degrees, or null): the ground layers (land, town, green, aeroway: whole-region meshes of up to a
//   million triangles, never culled) cast through caster-only copies holding just their faces steeper than the
//   sun's elevation less this margin, on a layer only the sun's shadow camera draws. A heightfield shades a point
//   only where the ray towards the sun enters the ground again, and there the ground rises at least as steeply as
//   the ray; the flat faces in between only ever shadowed themselves. Rebuilt when the sun's elevation crosses a
//   2-degree step; with the sun low (dusk) the copy holds nearly everything.
// fit (boolean): building and bridge tiles whose box, seen from the sun, lies wholly outside what the view (and the
//   water's mirror) can see of the shadow map's square are left out of the shadow pass. The map's projection is
//   not changed (the same texels, the same filtering): only casters whose shadows could fall nowhere on screen go.
//   The receivers are the view's frustum (truncated beyond the map's reach) cut to the height band anything stands
//   in, and its mirror image in the water's plane, projected on the sun's view plane; a margin of a few texels
//   keeps the filter's footprint.
import * as THREE from 'three/webgpu';

export const SHADOW_ONLY_LAYER = 6;          // drawn by the sun's shadow camera alone (main.js enables it there)

const _v = new THREE.Vector3(), _m = new THREE.Matrix4();
const CORNERS = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
// a truncated frustum's 12 edges (corners 0-3 near, 4-7 far)
const EDGES = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]];

export function createShadowTrim({ sun, opts = {}, mirrorY = 0 }) {
  let steepMargin = opts.groundSteep ?? null;
  let fit = !!opts.fit;
  const ground = [];                         // { mesh, caster, slope: Float32Array (degrees per face), idx, n }
  let steepAt = null;                        // the threshold the casters hold now (degrees)
  let yMin = Infinity, yMax = -Infinity;     // the height band receivers stand in (ground and tiles)
  const culled = [];
  const stats = { steepTris: 0, groundTris: 0, culled: 0, kept: 0 };

  // a ground layer: its caster-only copy (the faces steep enough), the layer itself no longer casting
  function addGround(mesh) {
    mesh.updateWorldMatrix(true, false);
    const box = new THREE.Box3().setFromObject(mesh);
    yMin = Math.min(yMin, box.min.y); yMax = Math.max(yMax, box.max.y);
    if (!mesh.castShadow) return;
    ground.push({ mesh });
    if (steepMargin !== null) makeCaster(ground.at(-1));
  }
  function makeCaster(gr) {
    const mesh = gr.mesh, g = mesh.geometry, pos = g.attributes.position, idx = g.index;
    const n = idx ? idx.count / 3 : pos.count / 3;
    const slope = new Float32Array(n);
    const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), e = mesh.matrixWorld;
    for (let f = 0; f < n; f++) {
      const i0 = idx ? idx.getX(3 * f) : 3 * f, i1 = idx ? idx.getX(3 * f + 1) : 3 * f + 1, i2 = idx ? idx.getX(3 * f + 2) : 3 * f + 2;
      a.fromBufferAttribute(pos, i0).applyMatrix4(e);
      b.fromBufferAttribute(pos, i1).applyMatrix4(e).sub(a);
      c.fromBufferAttribute(pos, i2).applyMatrix4(e).sub(a);
      b.cross(c);
      const l = b.length();
      slope[f] = l > 0 ? Math.acos(Math.min(1, Math.abs(b.y) / l)) * 180 / Math.PI : 90;
    }
    const geo = new THREE.BufferGeometry();
    for (const [k, attr] of Object.entries(g.attributes)) geo.setAttribute(k, attr);
    geo.boundingSphere = g.boundingSphere ?? (g.computeBoundingSphere(), g.boundingSphere);
    geo.boundingBox = g.boundingBox;
    const caster = new THREE.Mesh(geo, mesh.material);
    caster.name = `${mesh.name}-shadow`;
    caster.layers.set(SHADOW_ONLY_LAYER);
    caster.castShadow = true;
    caster.receiveShadow = false;
    caster.userData.noReflect = true;
    caster.userData.shadowOnly = true;
    caster.visible = false;                  // (until updateSun gives it its faces)
    mesh.castShadow = false;
    mesh.add(caster);
    Object.assign(gr, { caster, slope, idx, n });
    stats.groundTris += n;
    steepAt = null;
    if (lastElevation !== null) updateSun(lastElevation);
  }
  // (runtime switch, for measuring: null puts the layers back as they were)
  function setSteep(margin) {
    steepMargin = margin;
    for (const gr of ground) {
      if (margin !== null && !gr.caster) makeCaster(gr);
      if (!gr.caster) continue;
      gr.mesh.castShadow = margin === null;
      gr.caster.visible = false;
    }
    steepAt = null;
    if (margin !== null && lastElevation !== null) updateSun(lastElevation);
  }

  // the casters of the sun's elevation (degrees): faces steeper than it less the margin
  let lastElevation = null;
  function updateSun(elevation) {
    lastElevation = elevation;
    if (steepMargin === null || !ground.length) return;
    const want = Math.max(0, Math.floor((elevation - steepMargin) / 2) * 2);
    if (want === steepAt) return;
    steepAt = want;
    stats.steepTris = 0;
    for (const gr of ground) {
      const { slope, idx, n } = gr;
      let k = 0;
      for (let f = 0; f < n; f++) if (slope[f] >= want) k++;
      // (one index the size of the layer's, filled from the start, drawn up to the steep faces' count: no new
      // buffer per change of the sun)
      const geo = gr.caster.geometry;
      if (!geo.index) {
        const big = geo.attributes.position.count > 65535;
        geo.setIndex(new THREE.BufferAttribute(big ? new Uint32Array(3 * n) : new Uint16Array(3 * n), 1));
      }
      const out = geo.index.array;
      let o = 0;
      for (let f = 0; f < n; f++) {
        if (slope[f] < want) continue;
        if (idx) { out[o++] = idx.getX(3 * f); out[o++] = idx.getX(3 * f + 1); out[o++] = idx.getX(3 * f + 2); }
        else { out[o++] = 3 * f; out[o++] = 3 * f + 1; out[o++] = 3 * f + 2; }
      }
      out.fill(0, o);
      geo.index.needsUpdate = true;
      geo.setDrawRange(0, o);
      gr.caster.visible = k > 0;
      stats.steepTris += k;
    }
  }

  // a building tile's casters, with their boxes (while its arrays are still there)
  function addTile(root) {
    const casters = [];
    root.updateWorldMatrix(true, true);
    root.traverse((o) => {
      if (!o.isMesh || !o.castShadow) return;
      const box = new THREE.Box3().setFromObject(o);
      if (box.isEmpty()) return;
      casters.push({ mesh: o, box });
      yMin = Math.min(yMin, box.min.y); yMax = Math.max(yMax, box.max.y);
    });
    if (casters.length) root.userData.shadowCasters = casters;
  }

  // the receivers' rectangle on the sun's view plane: [x0, x1, y0, y1] in the shadow camera's view space
  const pts = [], corner = [...Array(8)].map(() => new THREE.Vector3());
  function receiverRect(camera, mirror, reach) {
    const cam = sun.shadow.camera;
    const tanV = Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) / camera.zoom, tanH = tanV * camera.aspect;
    camera.updateMatrixWorld();
    pts.length = 0;
    const lo = yMin - 5, hi = yMax + 40;     // (+40: trees and rooftop items over the tallest tile's box)
    for (const flip of mirror ? [false, true] : [false]) {
      for (let i = 0; i < 8; i++) {
        const d = i < 4 ? camera.near : reach;
        const [sx, sy] = CORNERS[i & 3];
        corner[i].set(sx * tanH * d, sy * tanV * d, -d).applyMatrix4(camera.matrixWorld);
        if (flip) corner[i].y = 2 * mirrorY - corner[i].y;
      }
      for (const p of corner) if (p.y >= lo && p.y <= hi) pts.push(p.clone());
      for (const [i, j] of EDGES) {
        const a = corner[i], b = corner[j];
        for (const h of [lo, hi]) {
          if ((a.y - h) * (b.y - h) >= 0) continue;
          pts.push(a.clone().lerp(b, (h - a.y) / (b.y - a.y)));
        }
      }
    }
    if (!pts.length) return null;
    const r = [Infinity, -Infinity, Infinity, -Infinity];
    for (const p of pts) {
      p.applyMatrix4(cam.matrixWorldInverse);
      r[0] = Math.min(r[0], p.x); r[1] = Math.max(r[1], p.x); r[2] = Math.min(r[2], p.y); r[3] = Math.max(r[3], p.y);
    }
    return r;
  }

  // before a frame that draws the shadow map: the tiles that can't shadow anything seen leave the pass
  function cull(camera, groups, { mirror = false, target } = {}) {
    if (!fit || culled.length) return 0;
    const cam = sun.shadow.camera;
    sun.updateMatrixWorld(); sun.target.updateMatrixWorld();
    sun.shadow.updateMatrices(sun);
    const span = cam.right;
    const reach = camera.position.distanceTo(target) + 1.5 * span + (yMax - yMin) + 100;
    const r = receiverRect(camera, mirror, reach);
    const texel = (2 * span) / sun.shadow.mapSize.x;
    const m = 4 * texel + 2;
    const x0 = Math.max(-span, (r?.[0] ?? 0) - m), x1 = Math.min(span, (r?.[1] ?? 0) + m);
    const y0 = Math.max(-span, (r?.[2] ?? 0) - m), y1 = Math.min(span, (r?.[3] ?? 0) + m);
    const none = !r || x0 > x1 || y0 > y1;
    _m.copy(cam.matrixWorldInverse);
    stats.culled = stats.kept = 0;
    for (const g of groups) {
      if (!g.visible || !g.userData.shadowCasters) continue;
      for (const c of g.userData.shadowCasters) {
        if (!c.mesh.castShadow) continue;
        let out = none;
        if (!out) {
          let bx0 = Infinity, bx1 = -Infinity, by0 = Infinity, by1 = -Infinity;
          const { min, max } = c.box;
          for (let i = 0; i < 8; i++) {
            _v.set(i & 1 ? max.x : min.x, i & 2 ? max.y : min.y, i & 4 ? max.z : min.z).applyMatrix4(_m);
            bx0 = Math.min(bx0, _v.x); bx1 = Math.max(bx1, _v.x); by0 = Math.min(by0, _v.y); by1 = Math.max(by1, _v.y);
          }
          out = bx1 < x0 || bx0 > x1 || by1 < y0 || by0 > y1;
        }
        if (out) { c.mesh.castShadow = false; culled.push(c.mesh); stats.culled++; } else stats.kept++;
      }
    }
    return culled.length;
  }
  function restore() {
    for (const o of culled) o.castShadow = true;
    culled.length = 0;
  }

  return { addGround, addTile, updateSun, cull, restore, stats, setSteep, setFit: (on) => { fit = on; },
    get fit() { return fit; }, get steep() { return steepMargin; }, steepAt: () => steepAt };
}
