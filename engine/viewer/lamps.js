// lamps.js: real street lamps after dark, from a city's lighting inventory (06e_lamps: web/lamps/lamps.json,
// lamps.bin, mask.bin; Paris: the Ville de Paris "Eclairage public", 110,000 open-air lamps). Without the
// files the viewer keeps its procedural posts (ground.js) everywhere.
//
// Each lamp is one instance of two quads: a pool of light lying on the street under it (as wide as twice its
// height, cut where the ground falls away: 06e_lamps) and its head's glow, a small disc facing the camera at its
// height. Colour from the lamp's colour temperature (low-pressure sodium: monochrome orange), brightness from its
// flux over its height squared. Drawn additively (the light a pool adds to the dark street; the street's own
// colour is taken as a mean paving grey), without depth writes, after the scene's opaque meshes, one draw call
// per 2 km chunk. A pool or head smaller than a few pixels grows to that and dims by as much, so a distant
// street keeps its mean light, a line of soft glow rather than a shimmer of dots.
//
// Only drawn while the city's lights are on (setOn: main.js's nightOn); by day the meshes are hidden and cost
// nothing. mask(xz): the inventory's coverage (0..1), for ground.js to leave out its procedural posts there.
import * as THREE from 'three/webgpu';
import { attribute, float, vec2, vec3, vec4, uniform, varying, cameraPosition, normalize, cross, length, max, min, exp,
  smoothstep, select, texture, positionWorld, clamp, mix } from 'three/tsl';

// linear lamp colours by colour temperature (region_research.md 6.1: blackbody, a little whitened)
const KELVIN = [[1800, [1, 0.35, 0.05]], [2000, [1, 0.36, 0.06]], [2200, [1, 0.4, 0.1]], [2700, [1, 0.5, 0.19]],
  [3000, [1, 0.57, 0.27]], [3500, [1, 0.66, 0.4]], [4000, [1, 0.75, 0.53]], [5000, [0.95, 0.85, 0.75]]];
const LPS = [1, 0.42, 0.0];
// (lamps.white's target: a near-neutral white, a touch warm)
const NEUTRAL = [1, 0.88, 0.74];              // low-pressure sodium, 589 nm
// a gas mantle (06e_lamps code 2: Berlin's gas lamps): the Auer mantle's warm light with its yellow-green cast, the
// "green-gold" of Berlin's gas-lit side streets, dimmer than LED (its flux)
const GAS = [0.9, 0.78, 0.3];
function kelvin(k) {
  if (k <= KELVIN[0][0]) return KELVIN[0][1];
  for (let i = 1; i < KELVIN.length; i++) {
    const [k1, c1] = KELVIN[i];
    if (k <= k1) { const [k0, c0] = KELVIN[i - 1], t = (k - k0) / (k1 - k0); return c0.map((v, j) => v + (c1[j] - v) * t); }
  }
  return KELVIN[KELVIN.length - 1][1];
}

export async function loadLamps(url = 'lamps/') {
  const index = await fetch(url + 'lamps.json', { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (!index) return null;
  const [bin, maskBuf] = await Promise.all([
    fetch(url + 'lamps.bin').then((r) => r.arrayBuffer()).then(gunzip),
    fetch(url + 'mask.bin').then((r) => r.arrayBuffer()),
  ]);
  const M = index.mask;
  const maskTex = new THREE.DataTexture(new Uint8Array(maskBuf), M.nx, M.nz, THREE.RedFormat, THREE.UnsignedByteType);
  maskTex.minFilter = maskTex.magFilter = THREE.LinearFilter;
  maskTex.wrapS = maskTex.wrapT = THREE.ClampToEdgeWrapping;
  maskTex.unpackAlignment = 1;              // (rows of any width: WebGL 2)
  maskTex.needsUpdate = true;
  // (the coverage at a world position: 0 outside the mask's grid)
  const mask = () => {
    const uvm = vec2(positionWorld.x.sub(M.x0).div(M.nx * M.cell), positionWorld.z.sub(M.z0).div(M.nz * M.cell));
    const inside = uvm.x.greaterThan(0).and(uvm.x.lessThan(1)).and(uvm.y.greaterThan(0)).and(uvm.y.lessThan(1));
    return select(inside, texture(maskTex, uvm).r, float(0));
  };
  return { index, bin, mask, maskTex, streetLight: streetLightMap(index, bin) };
}

// The street lamps' light near the ground as a coarse map (8 m cells, 0..1, each lamp splatted over up to 12 m round
// it): what lights the lower walls of the buildings on its streets (facade.js's wash), and not those of courtyards
// and light wells, which no lamp lights. Returns a TSL function of a world position, 0 outside the map.
function streetLightMap(index, bin) {
  const M = index.mask, C = 8;
  const x0 = M.x0, z0 = M.z0, nx = Math.ceil(M.nx * M.cell / C), nz = Math.ceil(M.nz * M.cell / C);
  const acc = new Float32Array(nx * nz);
  const view = new DataView(bin);
  for (const ch of index.chunks) {
    let o = ch.offset * 10;
    for (let i = 0; i < ch.n; i++, o += 10) {
      const x = ch.x + view.getInt16(o, true) / 10, z = ch.z + view.getInt16(o + 2, true) / 10;
      const r = Math.min(12, Math.max(6, view.getUint8(o + 7) / 5 * 0.8));
      const ci = (x - x0) / C, cj = (z - z0) / C, rc = r / C;
      for (let j = Math.max(0, Math.floor(cj - rc)); j <= Math.min(nz - 1, Math.ceil(cj + rc)); j++) {
        for (let k = Math.max(0, Math.floor(ci - rc)); k <= Math.min(nx - 1, Math.ceil(ci + rc)); k++) {
          const d = Math.hypot(k + 0.5 - ci, j + 0.5 - cj) / rc;
          if (d < 1) acc[j * nx + k] += (1 - d * d);
        }
      }
    }
  }
  const data = new Uint8Array(nx * nz);
  for (let i = 0; i < data.length; i++) data[i] = Math.min(255, Math.round(Math.min(acc[i], 1) * 255));
  const tex = new THREE.DataTexture(data, nx, nz, THREE.RedFormat, THREE.UnsignedByteType);
  tex.minFilter = tex.magFilter = THREE.LinearFilter;
  tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
  tex.unpackAlignment = 1;
  tex.needsUpdate = true;
  return (p) => {
    const uvm = vec2(p.x.sub(x0).div(nx * C), p.z.sub(z0).div(nz * C));
    const inside = uvm.x.greaterThan(0).and(uvm.x.lessThan(1)).and(uvm.y.greaterThan(0)).and(uvm.y.lessThan(1));
    return select(inside, texture(tex, uvm).r, float(0));
  };
}

async function gunzip(buf) {
  const b = new Uint8Array(buf);
  if (b[0] !== 0x1f || b[1] !== 0x8b) return buf;
  return new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
}

// data: loadLamps()'s; night: night.js's uniforms; fog: the scene's FogExp2 (its density dims far lamps)
// strength: city.json's lamps.pool (the pool's brightness under a 7 m, 3,500 lm lamp) and lamps.head
// extra: lamps the inventory lacks, in scene metres: { lines: [{ from: [x, z], to: [x, z], n, y, h, kelvin, flux }],
// points: [{ at: [x, y, z], kelvin, flux, head, colour }] } (a line's n lamps evenly from end to end: a bridge's candelabra;
// a point with `head` (its glow's radius, m) is a bare light with no pool on the ground: a beacon; `colour` (linear
// rgb) instead of the kelvin's: a red aviation light up a tower)
// halo: the head's soft glow around its bright disc (0: none); pole: the faint lit line of its post under it
// far: how much faster than their size grows the grown heads and pools dim (their brightness times (true size /
// drawn size)^far on top of the area's own dimming; 0: a lamp's summed light the same at any distance)
// (the halo, whatever far is, fades out as the head grows past its size, see below)
// dim: [[x, z, radius, k], ...] circles (scene metres) inside which the inventory's lamps shine at k of their light (the
// Bois de Boulogne's and de Vincennes' drives: the woods are the darkest places in aerial night photos, and lit at the
// full rate their lamp rows glowed like boulevards), fading to full over the last 150 m
// spread: the pools' size times this (their falloff as from a lamp that much higher, their edge that much further out;
// 1: as before): spaced lamps' pools on a bridge or a wide road overlap into a lit carriageway instead of a row of
// hard discs (London M8: "polka dots"); the peak stays `pool`
// mirror: { px, gain } (null: as before): in the water's mirror (drawn at a fraction of the view's resolution and then
// smeared into streaks) a head is at least px pixels of the view across (its light spread over it, as when it grows
// anywhere) and gain times as bright: a bank's or a bridge's lamp row mirrors as long broken streaks (London M8: a
// sub-pixel head was averaged away in the half-resolution mirror and the Thames under the Embankment stayed black)
// cut: { spread } (null: as before): the pools 06e_lamps cut short (where the ground falls away: quays over the
// river, lamps on bridge decks, whose radius is under twice the lamp's height) take this spread instead of
// `spread`: widened like the rest, they hung half over the water again (London M8 round 2: Southwark, London and
// Westminster Bridges' pools as "fried eggs" on the Thames)
// white: LED and fluorescent lamps' colour (by kelvin, not sodium or gas) taken this share of the way to a near-neutral
// white (0: the blackbody colours): a 3,000 K LED on pale paving reads near white after the tone mapping, and the
// blackbody orange made every LED street the sodium streets' amber (Berlin M8 fix round: no LED/sodium/gas mix)
// falloff: the pool's power law (h^2 / (h^2 + r^2))^falloff (1.5: a cosine over the inverse square); higher, a brighter
// spot under the lamp and darker between lamps, pools that show instead of an even wash
// beaconPx: the least size of a bare light's head (an aviation light), pixels
// headFar: [d0, d1] metres (null: none): the heads' beads fade out between those distances, the pools' mean light (a
// street's glow) stays: a lamp line far off reads as filtered glow, not a string of beads
export function createLamps(data, { night, fog, pool = 0.22, head = 5, extra = null, halo = 0, pole = 0, far = 0, dim = [], spread = 1, mirror = null, cut = null,
  white = 0, falloff = 1.5, headFar = null, beaconPx = 1.5, farGain = null }) {
  const { index, bin } = data;
  const view = new DataView(bin);
  const group = new THREE.Group();
  group.name = 'lamps';
  group.visible = false;
  let lit = false, enabled = true;
  // the base: a pool quad (corner.z 0) and a head quad (1), corners -1..1
  const base = new THREE.InstancedBufferGeometry();
  const c = [];
  // (and with `pole`, a third: the post, corner.z 2)
  const parts = pole ? [0, 1, 2] : [0, 1];
  for (const part of parts) for (const [x, y] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) c.push(x, y, part);
  base.setAttribute('corner', new THREE.Float32BufferAttribute(c, 3));
  // (double-sided for the heads, whatever the camera; the pools collapse instead when the camera is below
  // them: the water's mirror)
  base.setIndex(parts.flatMap((p) => [0, 2, 1, 0, 3, 2].map((i) => i + 4 * p)));
  base.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(12 * parts.length), 3));

  // metres per pixel per metre of distance (2 tan(fov / 2) / the drawing buffer's height), per render
  const pxK = uniform(0.001).onRenderUpdate(({ camera, renderer }) => {
    const h = renderer.getDrawingBufferSize(_v).y || 1000;
    return 2 * Math.tan(THREE.MathUtils.degToRad((camera.fov ?? 45) / 2)) / h;
  });
  const density = uniform(0).onRenderUpdate(() => fog?.density ?? 0);
  const poolK = uniform(pool), headK = uniform(head), mirrorK = uniform(mirror?.gain ?? 1);
  // farGain: { from, to, head, pool } (null: none): the heads and pools brighter by up to those factors with distance,
  // ramping in between from and to (m): a far overview's street web, whose 1.5-pixel heads and 3-pixel pools hold
  // too little light to show, without brightening the near views (Berlin M10 fix round: the 13 km night overview
  // at mean luma 7.8/255; far, the other knob, brightens the mid distances too)
  const headFarK = uniform(farGain?.head ?? 1), poolFarK = uniform(farGain?.pool ?? 1);

  const P = attribute('lampP', 'vec3'), D = attribute('lampD', 'vec4'), C = attribute('lampC', 'vec3');
  const corner = attribute('corner', 'vec3');
  const h = D.x, R = spread === 1 ? D.y : D.y.mul(spread), flux = D.z, bare = D.w;          // (bare > 0: a head of that radius, no pool)
  const toCam = cameraPosition.sub(P);
  const dist = length(toCam);
  const pix = dist.mul(pxK);
  // pool: at least 3 pixels across, its light spread over it
  const Rp = max(R, pix.mul(3));
  const under = cameraPosition.y.lessThan(P.y.sub(0.2));        // (the mirror's camera: no pool seen from below)
  const poolPos = P.add(vec3(corner.x.mul(Rp), 0, corner.y.mul(Rp)).mul(select(under.or(bare.greaterThan(0)), float(0), float(1))));
  // head: a disc of 0.3 m (a bare light's own size), at least 1.5 pixels; with a halo the quad is 4 times as wide
  // for the soft glow round it. In the water's mirror (the camera below) it stretches 5 times down the view's
  // vertical: the long streak rippled water draws of a light
  const own = select(bare.greaterThan(0), bare, float(0.3));
  // (beaconPx: bare lights (extra points with a head: aviation lights) at least that many pixels across, not 1.5: Berlin
  // M8 fix round, the Fernsehturm's red lights vanished at the overview)
  const minPx = beaconPx === 1.5 ? float(1.5) : select(bare.greaterThan(0), float(beaconPx), float(1.5));
  const S = mirror ? max(own, pix.mul(select(under, float(mirror.px ?? 4), minPx))) : max(own, pix.mul(minPx));
  const HQ0 = halo ? 4 : 1;
  // (the halo fades as the head grows past 1.5 times its size, gone at 4 times, and the quad shrinks with it
  // to the bare disc's: far lamps' quads were 4 times as wide for a glow no longer drawn, a sixteenth of their pixels)
  const haloFade = halo ? float(1).sub(smoothstep(float(1.5), float(4), S.div(own))) : float(1);
  const HQ = halo ? haloFade.mul(3).add(1) : float(HQ0);
  const dir = toCam.div(max(dist, 1e-3));
  const right = normalize(cross(vec3(0, 1, 0), dir));
  const up = cross(dir, right);
  const top = P.add(vec3(0, h, 0)).add(dir.mul(0.3));
  const stretch = select(under, float(5), float(1));
  const headPos = top.add(right.mul(corner.x.mul(S).mul(HQ))).add(up.mul(corner.y.mul(S).mul(HQ).mul(stretch)));
  // pole: a line from the foot to the head, 0.12 m wide (at least a pixel), facing the camera
  const PW = max(float(0.06), pix.mul(0.5));
  const polePos = P.add(vec3(0, corner.y.add(1).mul(0.5).mul(h.sub(0.2)), 0)).add(right.mul(corner.x.mul(PW)))
    .mul(select(under.or(bare.greaterThan(0)), float(0), float(1)));
  const isHead = corner.z;
  const m = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, side: THREE.DoubleSide });
  m.name = 'lamps';
  m.userData.uniforms = { poolK, headK, mirrorK, headFarK, poolFarK };          // (for trying things out from the console)
  m.blending = THREE.AdditiveBlending;
  m.fog = false;
  m.toneMapped = true;
  m.positionNode = select(isHead.greaterThan(1.5), polePos, select(isHead.greaterThan(0.5), headPos, poolPos));
  // per lamp: where in its pool or head (in the pool's own metres: the shape keeps its size, only dims when grown)
  const q = varying(corner.xy.mul(select(isHead.greaterThan(0.5), HQ, R)));
  const shrink = varying(select(isHead.greaterThan(1.5), PW.reciprocal().mul(0.06).mul(corner.y.add(1).mul(0.5).pow(2).add(0.02)),
    select(isHead.greaterThan(0.5), own.div(S).pow(2 + far).div(stretch).mul(mirror ? select(under, mirrorK, float(1)) : float(1)), R.div(Rp).pow(2 + far))));
  // (the halo only while the head is drawn near its true size, gone once it is grown 4 times)
  const haloK = varying(haloFade.mul(halo));
  // brightness under the lamp: flux (per 3,500 lm) over height squared (per 7 m); kept within 0.3-3
  const bright = varying(clamp(flux.div(3500).mul(float(49).div(h.mul(h))), 0.3, 3));
  const fade = varying(exp(density.mul(dist).pow(2).negate()));
  const vHead = varying(isHead);
  const vh = varying(spread === 1 ? h : h.mul(spread)), vR = varying(R);
  const r2 = q.dot(q);
  // the pool: the lamp's light on the ground, falling off with the cosine and the inverse square of the distance
  // (h^3 / d^3), taken smoothly to nothing at its radius (no rim: a light, not a decal)
  const lampAt = vh.mul(vh).div(r2.add(vh.mul(vh))).pow(falloff);
  const t = clamp(r2.div(vR.mul(vR)), 0, 1);
  const edge = float(1).sub(t).pow(2);
  const farT = farGain ? varying(smoothstep(float(farGain.from ?? 3000), float(farGain.to ?? 12000), dist)) : null;
  const poolE = lampAt.mul(edge).mul(bright).mul(poolK).mul(farGain ? mix(float(1), poolFarK, farT) : float(1));
  // the head: its bright disc, and a halo (the glow of the lamp in the night's haze) fading over 4 x its size
  const headE = exp(r2.mul(-7)).add(halo ? exp(r2.sqrt().mul(-2.2)).mul(haloK) : float(0)).mul(headK).mul(bright.sqrt())
    .mul(farGain ? mix(float(1), headFarK, farT) : float(1));
  const poleE = bright.sqrt().mul(headK).mul(pole);
  const headFade = headFar ? varying(max(float(1).sub(smoothstep(float(headFar[0]), float(headFar[1]), dist)), select(bare.greaterThan(0), float(1), float(0)))) : float(1);
  const e = select(vHead.greaterThan(1.5), poleE, select(vHead.greaterThan(0.5), headE.mul(headFade), poolE)).mul(shrink).mul(fade).mul(night.lampLights ?? night.lights);
  m.colorNode = vec4(varying(C).mul(e), 1);

  // the extra lamps (city.json lamps.extra) as one more chunk
  const ex = [];
  for (const l of extra?.lines ?? []) {
    for (let i = 0; i < l.n; i++) {
      const f = l.n > 1 ? i / (l.n - 1) : 0.5;
      ex.push([l.from[0] + (l.to[0] - l.from[0]) * f, l.y, l.from[1] + (l.to[1] - l.from[1]) * f, l.h ?? 4, 2 * (l.h ?? 4), l.flux ?? 2500, 0, l.kelvin ?? 2700]);
    }
  }
  for (const p of extra?.points ?? []) ex.push([p.at[0], p.at[1], p.at[2], p.h ?? 0.5, 2 * (p.h ?? 0.5), p.flux ?? 3500, p.head ?? 0, p.colour ?? p.kelvin ?? 3000]);
  const chunks = [...index.chunks];
  if (ex.length) {
    let sx = 0, sz = 0;
    for (const e of ex) { sx += e[0]; sz += e[2]; }
    chunks.push({ extra: true, n: ex.length, x: sx / ex.length, z: sz / ex.length });
  }
  // chunks
  const meshes = [];
  for (const ch of chunks) {
    const n = ch.n, lp = new Float32Array(n * 3), ld = new Float32Array(n * 4), lc = new Float32Array(n * 3);
    let o = (ch.offset ?? 0) * 10;
    let minY = Infinity, maxY = -Infinity, reach = index.chunk / 2 + 30 + 51 * Math.max(0, spread - 1);
    for (let i = 0; i < n; i++, o += 10) {
      if (ch.extra) {
        const [x, y, z, hh, rr, fl, bare, k] = ex[i];
        lp.set([x, y, z], i * 3);
        ld.set([hh, rr, fl, bare], i * 4);
        lc.set(Array.isArray(k) ? k : kelvin(k), i * 3);          // (a point's own colour: a red aviation light)
        minY = Math.min(minY, y); maxY = Math.max(maxY, y + hh);
        reach = Math.max(reach, Math.abs(x - ch.x) + rr * spread + 30, Math.abs(z - ch.z) + rr * spread + 30);
        continue;
      }
      const x = ch.x + view.getInt16(o, true) / 10, z = ch.z + view.getInt16(o + 2, true) / 10, y = view.getInt16(o + 4, true) / 10;
      const hh = view.getUint8(o + 6) / 10, rr = view.getUint8(o + 7) / 5, code = view.getUint8(o + 8), fl = view.getUint8(o + 9) * 100;
      lp.set([x, y, z], i * 3);
      ld.set([hh, cut && rr < 2 * hh - 0.3 ? rr * cut.spread / spread : rr, fl, 0], i * 4);
      lc.set(code === 1 ? LPS : code === 2 ? GAS : white ? kelvin(code * 100).map((v, j) => v + (NEUTRAL[j] - v) * white) : kelvin(code * 100), i * 3);
      if (dim.length) {
        let k = 1;
        for (const [dx, dz, dr, dk] of dim) k = Math.min(k, dk + (1 - dk) * THREE.MathUtils.smoothstep(Math.hypot(x - dx, z - dz), dr - 150, dr));
        if (k < 1) for (let j = 0; j < 3; j++) lc[i * 3 + j] *= k;
      }
      minY = Math.min(minY, y); maxY = Math.max(maxY, y + hh);
    }
    const g = new THREE.InstancedBufferGeometry();
    g.setIndex(base.index);
    g.setAttribute('corner', base.attributes.corner);
    g.setAttribute('position', base.attributes.position);
    g.setAttribute('lampP', new THREE.InstancedBufferAttribute(lp, 3));
    g.setAttribute('lampD', new THREE.InstancedBufferAttribute(ld, 4));
    g.setAttribute('lampC', new THREE.InstancedBufferAttribute(lc, 3));
    g.instanceCount = n;
    // (bounds for frustum culling: the chunk's square, its lamps' heights, the pools' reach)
    const half = reach;
    g.boundingBox = new THREE.Box3(new THREE.Vector3(ch.x - half, minY - 1, ch.z - half), new THREE.Vector3(ch.x + half, maxY + 2, ch.z + half));
    g.boundingSphere = g.boundingBox.getBoundingSphere(new THREE.Sphere());
    const mesh = new THREE.Mesh(g, m);
    mesh.name = 'lamps';
    mesh.renderOrder = 2;
    mesh.castShadow = mesh.receiveShadow = false;
    group.add(mesh);
    meshes.push(mesh);
  }
  return {
    group, meshes, material: m, count: index.count,
    // the lights' schedule turns them on after dark (main.js's nightOn); the menu's Lamps switch can keep them off
    setOn(on) { lit = !!on; group.visible = lit && enabled; },
    setEnabled(on) { enabled = !!on; group.visible = lit && enabled; },
    get enabled() { return enabled; },
    uniforms: { poolK, headK },
  };
}
const _v = new THREE.Vector2();
