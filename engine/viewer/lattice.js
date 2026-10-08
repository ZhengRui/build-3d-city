// lattice.js: the cut-out material of open iron lattices ([[structures]] kind lattice_tower: the Eiffel Tower).
// 06_tiles writes a tile's lattice panels as one `lattice` mesh: flat panels whose uv are pattern coordinates
// (legs and faces: across 0..1, up in face widths; spandrels and railings: metres over a period) and whose colour
// alpha is the pattern (0 braced panels, 1 spandrel ornament, 2 railings, 3 glazing, 4 fabric). The members are drawn as bars of a
// train at every integer of a coordinate, each box-filtered over the pixel's footprint (fwidth): near, crisp
// members with sky between them; far, where many bars share a pixel, the coverage settles to the lattice's mean
// density instead of shimmering (at dpr 1 and 2, WebGPU and WebGL 2 alike). The panels blend (transparent,
// no depth writes: the same paint behind and in front, so their order hardly shows), cast no shadow (the solid
// chords, arches and decks do) and stay out of the AO pre-pass (transparent). One draw call per tile.
// Night (M8): with night.js's goldTower colour set (Paris), a lit copy (night.u.withLights) glows gold, as the
// Eiffel Tower does under the sodium lamps inside its lattice, a little brighter towards the top; during the
// sparkle (night.u.sparkle: the first five minutes of the hour) white bulbs twinkle over it, a bulb every
// ~1.2 m on a member, their mean once they are smaller than a pixel (a frozen instant: the frame is only
// drawn again when the view changes).
import * as THREE from 'three/webgpu';
import { glowMask } from './night.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { attribute, uv, float, vec3, vec4, fwidth, floor, fract, min, max, select, mix, clamp, hash, positionWorld, smoothstep, length, vec2,
  exp, abs, dot as dotV, normalWorld, cameraPosition, normalize, frontFacing, uniform } from 'three/tsl';

// coverage of bars of width w (a share of the period) centred on every integer of s, over this pixel
function bars(s, w) {
  const W = float(w);
  const fw = max(fwidth(s).mul(1.25), float(1e-4));
  const cum = (y) => floor(y).mul(W).add(min(fract(y), W));     // how much of (-inf, y] is bar
  const y = s.add(W.mul(0.5));
  return clamp(cum(y.add(fw.mul(0.5))).sub(cum(y.sub(fw.mul(0.5)))).div(fw), 0, 1);
}
// several bar families over one another: 1 - the product of their gaps
const union = (...c) => float(1).sub(c.reduce((g, x) => g.mul(float(1).sub(x)), float(1)));

export function createLatticeMaterial({ roughness = 0.72, metalness = 0.15, density = 1, night = null } = {}) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness, metalness, side: THREE.DoubleSide, transparent: true });
  m.depthWrite = false;
  m.name = 'lattice';
  m.userData.lattice = true;             // (main.js ANIM_OVERLAY_LATTICE)
  const col = attribute('color', 'vec4');
  const kind = col.w.mul(255).round();
  const p = uv();
  const u = p.x, v = p.y;
  // braced panels: the big St Andrew's crosses (one per face width), the horizontals between them, the edges,
  // and the lacing within the members (a quarter the period, lighter): lace near, a brown veil far
  const brace = union(bars(u.sub(v), 0.1), bars(u.add(v), 0.1), bars(v, 0.09), bars(u, 0.08),
    bars(u.sub(v).mul(4), 0.18).mul(0.8), bars(u.add(v).mul(4), 0.18).mul(0.8), bars(v.mul(4), 0.12).mul(0.5),
    bars(u.sub(v).mul(12), 0.25).mul(0.45), bars(u.add(v).mul(12), 0.25).mul(0.45));
  // (the same as the main members and the lacing apart, for the lit tower after dark: night.goldLattice)
  const G = night?.goldLattice;
  const braceMain = G ? union(bars(u.sub(v), 0.1), bars(u.add(v), 0.1), bars(v, 0.09), bars(u, 0.08)) : null;
  const braceLace = G ? union(bars(u.sub(v).mul(4), 0.18).mul(0.8), bars(u.add(v).mul(4), 0.18).mul(0.8), bars(v.mul(4), 0.12).mul(0.5),
    bars(u.sub(v).mul(12), 0.25).mul(0.45), bars(u.add(v).mul(12), 0.25).mul(0.45)) : null;
  // spandrels (the ornament between the arches and the first deck): small diamonds, posts and rings of bars
  const ornament = union(bars(u.sub(v), 0.18), bars(u.add(v), 0.18), bars(u.mul(2), 0.12).mul(0.7), bars(v.mul(0.5), 0.14),
    bars(u.sub(v).mul(3), 0.2).mul(0.4), bars(u.add(v).mul(3), 0.2).mul(0.4));
  // railings: posts every period, a rail at the top and the foot
  const railing = union(bars(u, 0.1), bars(v, 0.08), bars(v.mul(3), 0.05).mul(0.5));
  const cover = select(kind.lessThan(0.5), brace, select(kind.lessThan(1.5), ornament, railing));
  // glazing (kind 3: a glass dome or vault, [[structures]] figure `glazing`): a grid of light steel members (uv: one
  // per period) over panes that let most of the light through; fabric (kind 4: a membrane on cables, the Sony
  // Center's tent): a translucent sheet with thin cables. The panes are the sheet's own colour darkened (glass) or
  // kept (fabric), at a fixed opacity; the members opaque
  const glazed = kind.greaterThan(2.5);
  const fabric = kind.greaterThan(3.5);
  const grid = select(fabric, union(bars(u, 0.035), bars(v, 0.03)), union(bars(u, 0.07), bars(v, 0.06)));
  const pane = select(fabric, float(0.62), float(0.45));
  const paneCol = select(fabric, col.xyz, col.xyz.mul(vec3(0.4, 0.46, 0.5)));
  const memberCol = select(fabric, col.xyz.mul(0.5), col.xyz);
  // the members' own shade: riveted plates and angles in each other's shadow, darker than a flat sheet
  m.colorNode = vec4(select(glazed, mix(paneCol, memberCol, grid), col.xyz.mul(mix(float(0.85), float(0.95), cover))), 1);
  m.opacityNode = select(glazed, max(grid, pane), clamp(cover.mul(density), 0, 1));
  m.alphaTest = 0.004;                   // (fully open pixels skip the blend)
  if (night) {
    // The gold is light, not paint: the sodium lamps stand at the foot of the pillars and on each platform
    // (night.goldLevels: their heights over night.goldBase, m) and shine up the lattice, so each stage is
    // brightest just above its lamps and fades upwards; members seen from behind (the far legs, the inside of a
    // pillar through its near face) take less of it; members seen edge-on catch it (a rim); a white bulb at the
    // top (lamps.js extras) is the beacon
    const lv = night.goldLevels ?? [];
    const dy = positionWorld.y.sub(night.goldBase ?? 0);
    let above = dy;
    for (const L of lv) above = select(dy.greaterThan(L), dy.sub(L), above);
    const fall = lv.length ? exp(max(above, 0).div(-40)).mul(0.75).add(0.45) : clamp(positionWorld.y.div(300), 0, 1).mul(0.35).add(0.85);
    const V = normalize(cameraPosition.sub(positionWorld));
    const facing = abs(dotV(normalWorld, V));
    const rim = float(1).sub(facing).pow(2).mul(0.6);
    const side = lv.length ? select(frontFacing, float(1), float(0.5)) : float(1);
    const gold = night.goldTower.mul(fall.mul(side).add(rim)).mul(mix(float(0.8), float(1.05), cover));
    // sparkle: cells of 1.2 m (world), one bulb each at a hashed spot, lit on one cell in four
    const cell = positionWorld.div(1.2);
    const id = floor(cell);
    const h = hash(id.x.add(id.y.mul(157)).add(id.z.mul(113)));
    const d = length(fract(cell).sub(vec3(h.mul(0.6).add(0.2), fract(h.mul(7.1)).mul(0.6).add(0.2), fract(h.mul(13.3)).mul(0.6).add(0.2))));
    const fw = max(fwidth(cell.x), max(fwidth(cell.y), fwidth(cell.z)));
    const dot = float(1).sub(smoothstep(0.08, 0.16, d)).mul(select(fract(h.mul(31.7)).lessThan(0.25), float(1), float(0)));
    const bulbs = mix(dot.mul(9), float(0.25 * 9 * 0.025), smoothstep(0.08, 0.3, fw));
    // landmark glows on the glazing and fabric (night.glows with on: 'lattice'): a membrane or a glass dome lit from
    // within (the Sony Center's tent, the Reichstag's dome; Berlin M8 fix round), its cables and members darker
    let glow = vec3(0, 0, 0);
    for (const g of (night.glows ?? []).filter((g) => g.on === 'lattice')) {
      glow = glow.add(vec3(...g.colour).mul(g.k ?? 1).mul(glowMask(g)).mul(mix(float(1), float(g.members ?? 0.35), grid)));
    }
    const glowOn = (night.glows ?? []).some((g) => g.on === 'lattice');
    // (left out of the glass's city reflection, a cube map drawn by 90-degree square cameras from one point: a bright
    // membrane in it smeared lavender over every facade whose reflection looked down, even the ones facing away)
    const notProbe = uniform(1).onRenderUpdate(({ camera }) => (camera.isPerspectiveCamera && camera.fov === 90 && camera.aspect === 1 ? 0 : 1));
    if (glowOn) glow = glow.mul(notProbe);
    if (!G) night.withLights(m, gold.add(vec3(0.9, 0.95, 1).mul(bulbs).mul(night.sparkle)).add(glowOn ? glow.mul(select(glazed, float(1), float(0))) : vec3(0, 0, 0)));
    else {
      // night.goldLattice (Paris, 7 Oct: the user found the tower "a flat, uniform, opaque golden coat"). The 336 sodium lamps
      // stand inside the structure and shine up and out through it: the members glow, the main ones (the big crosses,
      // the horizontals and the edges) more than the lacing within them, and the gaps between them stay open, dark
      // and see-through (the lacing's veil thinned to G.veil as the lights come on); each stage brightest just over
      // its lamps and under the deck above them, the upper shaft dimmer (G.stage); a panel seen from the side facing
      // the axis shows its lit inner face (the far faces through the near ones glow, the near faces' outer sides are
      // darker: the tower lit from within)
      const braceN = union(braceMain, braceLace.mul(G.veil));
      const lit = night.lights;
      const nightOpacity = select(glazed, max(grid, pane),
        clamp(mix(cover, select(kind.lessThan(0.5), braceN, cover), lit).mul(density), 0, 1));
      const memberK = select(kind.lessThan(0.5), mix(G.lace, float(1), clamp(braceMain.div(max(braceN, 1e-3)), 0, 1)), float(1));
      let sideK = float(1);
      if (G.at) {
        const toAxis = vec2(...G.at).sub(positionWorld.xz), toCam = cameraPosition.xz.sub(positionWorld.xz);
        const c = dotV(toAxis, toCam).div(max(length(toAxis).mul(length(toCam)), 1e-3));
        sideK = mix(G.outside, G.inside, smoothstep(-0.35, 0.35, c));
      }
      const goldN = (G.colour ? G.colour(positionWorld.y) : night.goldTower).mul(G.stage(positionWorld.y).mul(sideK).add(rim.mul(0.5))).mul(memberK);
      night.withNight(m, (litM) => {
        const extra = vec3(0.9, 0.95, 1).mul(bulbs).mul(night.sparkle).add(glowOn ? glow.mul(select(glazed, float(1), float(0))) : vec3(0, 0, 0));
        litM.emissiveNode = (m.emissiveNode ?? vec3(0, 0, 0)).add(goldN.add(extra).mul(night.lights));
        litM.opacityNode = nightOpacity;
      });
    }
  }
  return m;
}

// Broadcast masts beyond the tiles (city.json masts, default none): square lattice towers on the backdrop's hills,
// which 06_tiles' [[structures]] can't place (they lie outside the tiled ground: London's Crystal Palace transmitter
// 8.9 km south of the centre on the Norwood ridge, the Croydon mast on Beulah Hill, Alexandra Palace's to the
// north). Each: { name, x, z (scene m), height (the top, m over its foot), profile [[y, width], ...] (the lattice's
// square section bottom to top, m), mast [y0, radius] (a solid antenna from y0 to the top), turn (compass degrees
// of a face), lift (m: its foot over the ground: on a building's roof), plinth [width, height] (a solid block under
// it: Alexandra Palace's brick tower), colour }. Seen from 8-10 km they are a few pixels wide: the corner chords and
// the antenna solid, the faces the cut-out lattice (box-filtered to its mean density far off), no shadows.
// ground(x, z): the height of whatever they stand on (main.js: a ray down onto the backdrop)
export function createMasts(specs, latticeMaterial, ground) {
  const group = new THREE.Group();
  group.name = 'masts';
  const solids = new Map();
  const solidMat = (hex) => {
    if (!solids.has(hex)) solids.set(hex, new THREE.MeshStandardNodeMaterial({ color: new THREE.Color(hex), roughness: 0.75, metalness: 0.2 }));
    return solids.get(hex);
  };
  for (const s of specs) {
    const colour = new THREE.Color(s.colour ?? '#5e534c');
    const y0 = ground(s.x, s.z) + (s.lift ?? 0);
    const turn = THREE.MathUtils.degToRad(s.turn ?? 0);
    const prof = s.profile;
    // the faces: rows every ~face width (a bay as tall as it is wide), v in face widths up the face
    const rows = [];
    let v = 0;
    for (let i = 0; i < prof.length - 1; i++) {
      const [ya, wa] = prof[i], [yb, wb] = prof[i + 1];
      const n = Math.max(1, Math.round((yb - ya) / ((wa + wb) / 2)));
      for (let j = i ? 1 : 0; j <= n; j++) {
        const t = j / n, y = ya + (yb - ya) * t, w = wa + (wb - wa) * t;
        if (rows.length) { const p = rows[rows.length - 1]; v += (y - p.y) / ((w + p.w) / 2); }
        rows.push({ y, w, v });
      }
    }
    const pos = [], uv = [], col = [], idx = [];
    const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
    for (let f = 0; f < 4; f++) {
      const [ax, az] = corners[f], [bx, bz] = corners[(f + 1) % 4];
      const base = pos.length / 3;
      for (const r of rows) {
        for (const [cx, cz, u] of [[ax, az, 0], [bx, bz, 1]]) {
          pos.push(cx * r.w / 2, r.y, cz * r.w / 2);
          uv.push(u, r.v);
          col.push(colour.r, colour.g, colour.b, 0);
        }
      }
      for (let k = 0; k < rows.length - 1; k++) {
        const a = base + 2 * k;
        idx.push(a, a + 1, a + 3, a, a + 3, a + 2);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setAttribute('color', new THREE.Float32BufferAttribute(col, 4));
    g.setIndex(idx);
    g.computeVertexNormals();
    const tower = new THREE.Group();
    tower.position.set(s.x, y0, s.z);
    tower.rotation.y = -turn;
    tower.add(new THREE.Mesh(g, latticeMaterial));
    // the corner chords: a tapering square bar up each corner, a little over a twentieth of the section
    const solidParts = [];
    for (const [cx, cz] of corners) {
      for (let k = 0; k < rows.length - 1; k++) {
        const r0 = rows[k], r1 = rows[k + 1];
        const w = Math.max(0.5, r0.w * 0.06);
        const p0 = new THREE.Vector3(cx * r0.w / 2, r0.y, cz * r0.w / 2), p1 = new THREE.Vector3(cx * r1.w / 2, r1.y, cz * r1.w / 2);
        const len = p0.distanceTo(p1);
        const bar = new THREE.BoxGeometry(w, len, w);
        bar.translate(0, len / 2, 0);
        bar.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), p1.clone().sub(p0).normalize()));
        bar.translate(p0.x, p0.y, p0.z);
        solidParts.push(bar);
      }
    }
    // girder belts every few bays (the platforms), the antenna on top, a plinth under
    for (let k = 3; k < rows.length - 1; k += 4) {
      const r = rows[k];
      const belt = new THREE.BoxGeometry(r.w, Math.max(0.8, r.w * 0.06), r.w);
      belt.translate(0, r.y, 0);
      solidParts.push(belt);
    }
    if (s.mast) {
      const [m0, rad] = s.mast;
      const c = new THREE.CylinderGeometry(rad * 0.6, rad, s.height - m0, 8, 1);
      c.translate(0, (m0 + s.height) / 2, 0);
      solidParts.push(c);
    }
    if (s.plinth) {
      const [pw, ph] = s.plinth;
      const b = new THREE.BoxGeometry(pw, ph, pw);
      b.translate(0, -ph / 2, 0);
      solidParts.push(b);
    }
    const merged = mergeGeometries(solidParts.map((p) => (p.index ? p.toNonIndexed() : p)).map((p) => { p.deleteAttribute('uv'); return p; }));
    tower.add(new THREE.Mesh(merged, solidMat(s.colour ?? '#5e534c')));
    tower.traverse((o) => { o.castShadow = false; o.receiveShadow = false; o.userData.noReflect = true; });
    tower.name = s.name ?? 'mast';
    group.add(tower);
  }
  return group;
}
