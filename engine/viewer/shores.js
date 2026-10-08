// Shorelines (TSL): the strips 05e_shores.py lays along every edge between land and water, and the
// swimming pools. Each strip has bands across it, with texture coordinates (across, along) in metres
// (across grows towards the water) and COLOR_0 = (type, band, seed):
//   revetment   promenade paving with a granite coping, then a slope of rock armour (riprap): dry grey
//               blocks, a dark wet zone with algae and oyster crust towards the water line, and under the
//               water the toe of the slope fading into the murk
//   quay        concrete apron, a vertical wall with rubber fenders and a wet stain, dark water below it
//   beach       dry sand, wet darker sand down to the water, a broken line of swash and foam
//   mudflat     mangrove mud: a glistening grey-brown flat cut by drainage channels, fraying into the sea
//   embankment  rivers and canals: a concrete coping and wall, streaked and stained green at the foot
//   pondbank    park ponds: grass and soil edge with landscape boulders, stones and mud at the water,
//               shallow water showing the bottom, lotus and lily pads here and there
//   pondedge    ponds among paving (plazas, office parks): a granite coping and a short dark stone face
//   pool        pale stone coping; the pool itself turquoise with a darker deep end
//   quaywall    river quays ([shores] quay_walls): a limestone ashlar wall from under the water to the quay, a
//               granite-sett apron with a stone coping on top (its toe band is the quay's shadow on the water)
// The first two bands are opaque; the third (toe) lies over the water and is blended. Detail fades to its
// average once smaller than a pixel, as in ground.js. The slope bands carry shading normals (a 1:2
// revetment, a vertical quay) from the pipeline; individual rocks are shaded here from the sun's side.
import * as THREE from 'three/webgpu';
import {
  float, vec2, vec3, uint, uv, vertexColor, positionWorld, normalLocal, fwidth, hash,
  select, mix, smoothstep, clamp, max, min, abs, floor, fract, mod, dot, sin, dFdx, dFdy, uniform,
} from 'three/tsl';

const f01 = (c) => select(c, float(1), float(0));
const below = (lo, hi, x) => float(1).sub(smoothstep(lo, hi, x));

// ---------------------------------------------------------------- noise (as in ground.js)
const OFF = 65536 * 16;
const hashI = (ix, iz, salt = 0) => hash(
  mod(ix.add(OFF), 65536).toUint().mul(uint(0x9E3779B1))
    .bitXor(mod(iz.add(OFF), 65536).toUint().mul(uint(0x85EBCA77)))
    .add(uint(salt * 0x27D4EB2F >>> 0)));
function vnoise(p, salt = 0) {
  const i = floor(p), f = fract(p);
  const u = f.mul(f).mul(f.mul(-2).add(3));
  const a = hashI(i.x, i.y, salt), b = hashI(i.x.add(1), i.y, salt);
  const c = hashI(i.x, i.y.add(1), salt), d = hashI(i.x.add(1), i.y.add(1), salt);
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
const resolved = (fw, freq = 1) => float(1).sub(smoothstep(0.3, 0.9, fw.mul(freq)));
function fbm(p, fw, octaves = 3, salt = 0) {
  let sum = float(0), norm = 0, amp = 1, f = 1;
  for (let i = 0; i < octaves; i++) {
    sum = sum.add(mix(float(0.5), vnoise(p.mul(f), salt + i * 101), resolved(fw, f)).mul(amp));
    norm += amp;
    amp *= 0.5;
    f *= 2.03;
  }
  return sum.div(norm);
}
// nearest jittered point of a unit grid: squared distance, offset to it, random id (branchless 3 x 3)
function worley(p, salt) {
  const i = floor(p), f = fract(p);
  let best = float(9), id = float(0), off = vec2(0, 0);
  for (let dx = -1; dx <= 1; dx++) {
    for (let dy = -1; dy <= 1; dy++) {
      const cx = i.x.add(dx), cy = i.y.add(dy);
      const j = vec2(hashI(cx, cy, salt), hashI(cx, cy, salt + 1)).mul(0.8).add(0.1);
      const o = vec2(dx, dy).add(j).sub(f);
      const d = dot(o, o);
      const closer = f01(d.lessThan(best));
      best = mix(best, d, closer);
      id = mix(id, hashI(cx, cy, salt + 2), closer);
      off = mix(off, o, closer);
    }
  }
  return { d2: best, id, off };
}

// the same, with the second nearest point too: the gap between two cells (s1 - s0, 0 on their border)
// makes blocks with straight, broken edges instead of round cobbles
function worley2(p, salt) {
  const i = floor(p), f = fract(p);
  let d0 = float(9), d1 = float(9), id = float(0), off = vec2(0, 0);
  for (let dx = -1; dx <= 1; dx++) {
    for (let dy = -1; dy <= 1; dy++) {
      const cx = i.x.add(dx), cy = i.y.add(dy);
      const j = vec2(hashI(cx, cy, salt), hashI(cx, cy, salt + 1)).mul(0.8).add(0.1);
      const o = vec2(dx, dy).add(j).sub(f);
      const d = dot(o, o);
      const closer = f01(d.lessThan(d0));
      d1 = mix(min(d1, d), d0, closer);
      d0 = mix(d0, d, closer);
      id = mix(id, hashI(cx, cy, salt + 2), closer);
      off = mix(off, o, closer);
    }
  }
  return { d0, d1, id, off, gap: d1.sqrt().sub(d0.sqrt()) };
}

// ---------------------------------------------------------------- shared inputs
const TYPE = { revetment: 0, quay: 1, beach: 2, mudflat: 3, embankment: 4, pondbank: 5, pool: 6, pondedge: 7, quaywall: 8 };
const code = vertexColor().mul(255).add(0.5).floor();
const type = code.x, band = code.y, seed = code.z.div(255);
const is = (t) => f01(abs(type.sub(t)).lessThan(0.5));
const A = uv().x, S = uv().y;                      // across (m, + towards the water), along (m)
const fwA = max(fwidth(A), 1e-4), fwS = max(fwidth(S), 1e-4);
const fw = max(fwA, fwS);
const AS = vec2(A, S.add(seed.mul(997)));          // pattern space, shifted per run
// seaward and along directions in the world: from the shading normal of slope bands; on flat bands from
// how across changes over the screen against the world position (the gradient of across)
const nrm = normalLocal;                           // the strips are not transformed: local = world
const Pw = positionWorld.xz;
const dPx = dFdx(Pw), dPy = dFdy(Pw), dAx = dFdx(A), dAy = dFdy(A);
const gradA = vec2(dPy.y.mul(dAx).sub(dPx.y.mul(dAy)), dPx.x.mul(dAy).sub(dPy.x.mul(dAx)))
  .mul(select(dPx.x.mul(dPy.y).sub(dPx.y.mul(dPy.x)).lessThan(0), float(-1), float(1)));
const flatDir = gradA.div(max(gradA.length(), 1e-6));
const slopeDir = vec2(nrm.x, nrm.z).div(max(vec2(nrm.x, nrm.z).length(), 1e-4));
const seaward = mix(flatDir, slopeDir, smoothstep(0.02, 0.08, vec2(nrm.x, nrm.z).length()));
const alongDir = vec2(seaward.y, seaward.x.negate());

// Lighting of a bumpy surface relative to its flat self (the renderer lights the flat shading normal):
// rel = offset from the bump's centre in (across, along) units of its radius, height = bump height.
function bumpLight(rel, sun, height = 0.8) {
  const up = float(1).sub(dot(rel, rel)).max(0.03).sqrt().mul(height);
  const off = vec2(seaward.x, seaward.y).mul(rel.x).add(alongDir.mul(rel.y));
  const n = vec3(off.x.negate(), up, off.y.negate()).add(nrm.mul(0.6)).normalize();
  return clamp(dot(n, sun).div(max(dot(nrm, sun), 0.15)), 0.25, 1.8);
}

// ---------------------------------------------------------------- opaque bands
function shoreMaterial(sunDir) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.9, metalness: 0 });
  const sun = uniform(sunDir);                     // live: follows the time of day
  const b0 = f01(band.lessThan(0.5)), b1 = float(1).sub(b0);
  const grain = fbm(AS.div(vec2(0.7, 1.3)), fw.div(0.7), 3, 3);
  const stain = fbm(AS.div(vec2(3, 9)), fw.div(3), 3, 5);

  // --- revetment: promenade and coping (band 0), rock armour (band 1)
  const slab = hashI(floor(S.div(1.2)), floor(A.div(1.2)), 7);
  const joints = max(f01(fract(S.div(1.2)).lessThan(0.04)), f01(fract(A.div(1.2)).lessThan(0.04))).mul(resolved(fw, 1 / 1.2));
  const paving = mix(vec3(0.36, 0.35, 0.32), vec3(0.42, 0.4, 0.36), slab).mul(float(1).sub(joints.mul(0.25)))
    .mul(stain.sub(0.5).mul(0.3).add(1));
  const coping = vec3(0.5, 0.49, 0.45).mul(grain.sub(0.5).mul(0.2).add(1));
  // railing: a dark line with its shadow just inside the coping
  const rail = f01(A.greaterThan(-0.55).and(A.lessThan(-0.42))).mul(resolved(fwA, 8));
  let promenade = mix(paving, coping, f01(A.greaterThan(-0.45)));
  promenade = mix(promenade, vec3(0.08, 0.08, 0.08), rail.mul(0.7));
  // rock armour: quarried granite blocks of about a metre, dumped at random: angular, each broken into
  // two flat faces tilted its own way (lit from the sun's side as facets, not as domes), with dark
  // voids between the blocks. The pattern space is stretched and bent by noise so the blocks are not
  // laid out on a grid.
  const rq = AS.div(vec2(1.05, 1.3)).add(vec2(vnoise(AS.div(1.9), 91), vnoise(AS.div(1.9).add(7.1), 93)).sub(0.5).mul(0.6));
  const rock = worley2(rq, 11);
  const rh = (k) => hashI(floor(rock.id.mul(65521)), float(k), 101).sub(0.5);
  // two faces split by a line through the block at a random angle
  const splitA = rh(1).mul(6.283);
  const side = f01(dot(rock.off, vec2(sin(splitA), sin(splitA.add(1.5708)))).greaterThan(rh(2).mul(0.3)));
  const tilt = mix(vec2(rh(3), rh(4)), vec2(rh(5), rh(6)), side).mul(1.5);
  const facetN = vec3(seaward.x.mul(tilt.x).add(alongDir.x.mul(tilt.y)).negate(), float(1),
    seaward.y.mul(tilt.x).add(alongDir.y.mul(tilt.y)).negate()).add(nrm.mul(0.7)).normalize();
  const facetLit = clamp(dot(facetN, sun).div(max(dot(nrm, sun), 0.15)), 0.3, 1.7);
  // voids between blocks, wider in places (the blocks do not fit), and each block's edges falling
  // away into shade so it reads as a lump of stone rather than a paving slab
  const gap = below(0.03, vnoise(AS.div(2.3), 97).mul(0.2).add(0.1), rock.gap);
  const rockRes = resolved(fw.div(0.9), 3);
  const rockLit = mix(float(1), facetLit.mul(smoothstep(0.0, 0.4, rock.gap).mul(0.45).add(0.55)), rockRes);
  const rockTone = mix(vec3(0.27, 0.26, 0.245), vec3(0.44, 0.425, 0.39), rock.id.mul(rock.id))
    .mul(grain.sub(0.5).mul(0.35).add(1)).mul(float(1).add(rh(7).mul(0.12)));
  // wet zone: the lower part of the slope stays dark (spray, tides); a black-green algae and oyster
  // band at the water line, a pale band of barnacles above it
  const wet = smoothstep(1.8, 3.3, A.add(stain.sub(0.5).mul(1.2)));
  const algae = smoothstep(3.7, 4.6, A.add(stain.sub(0.5).mul(0.6)));
  let rocks = rockTone.mul(mix(float(1), float(0.4), wet));
  rocks = mix(rocks, vec3(0.05, 0.055, 0.035), algae.mul(0.85));
  rocks = mix(rocks, vec3(0.45, 0.44, 0.4), smoothstep(3.3, 3.6, A).mul(below(3.6, 4.0, A)).mul(0.25));
  rocks = rocks.mul(rockLit).mul(mix(float(1), float(0.12), gap.mul(rockRes)));
  const revet = mix(rocks, promenade, b0);

  // --- quay: concrete apron with a painted edge, vertical wall with fenders and a wet stain
  const apronSlab = hashI(floor(S.div(6)), floor(A.div(6)), 13);
  let apron = mix(vec3(0.33, 0.325, 0.31), vec3(0.38, 0.37, 0.35), apronSlab).mul(stain.sub(0.5).mul(0.4).add(1));
  apron = mix(apron, vec3(0.55, 0.5, 0.12), f01(A.greaterThan(-0.5).and(A.lessThan(-0.3))).mul(resolved(fwA, 5)).mul(0.6));
  // on the wall, height above the water comes from across (0 top .. 0.08 foot)
  const h = float(1).sub(A.div(0.08)).clamp(0, 1);
  const fender = f01(fract(S.div(14)).lessThan(0.09)).mul(f01(h.greaterThan(0.25)));
  let wall = vec3(0.3, 0.29, 0.27).mul(stain.sub(0.5).mul(0.5).add(1));
  wall = mix(wall, vec3(0.08, 0.075, 0.06), below(0.3, 0.55, h));
  wall = mix(wall, vec3(0.03, 0.03, 0.03), fender);
  const quay = mix(wall, apron, b0);

  // --- beach: dry pale sand, wet darker sand towards the water
  const ripples = mix(float(0.5), sin(A.mul(9).add(vnoise(AS.div(3), 17).mul(6))).mul(0.5).add(0.5), resolved(fwA, 1.5));
  const dry = vec3(0.47, 0.42, 0.33).mul(grain.sub(0.5).mul(0.2).add(1)).mul(ripples.mul(0.08).add(0.96));
  const wetSand = mix(vec3(0.33, 0.29, 0.22), vec3(0.2, 0.175, 0.13), smoothstep(2, 12, A)).mul(stain.sub(0.5).mul(0.2).add(1));
  const beach = mix(wetSand, mix(dry, wetSand, smoothstep(-2, 0, A)), b0);

  // --- mudflat edge: black mangrove mud with roots, glistening grey-brown mud sloping down
  const roots = f01(vnoise(AS.div(0.35), 19).greaterThan(0.62)).mul(resolved(fw, 3));
  const mangroveMud = mix(vec3(0.07, 0.065, 0.05), vec3(0.12, 0.1, 0.07), roots).mul(grain.sub(0.5).mul(0.3).add(1));
  const mudSlope = vec3(0.13, 0.115, 0.09).mul(stain.sub(0.5).mul(0.4).add(1));
  const mud = mix(mudSlope, mangroveMud, b0);

  // --- embankment: coping and a concrete wall, streaked, green-black at the foot
  const streak = fbm(vec2(S.div(1.3), A.div(12)), fwS.div(1.3), 2, 23);
  const copingC = vec3(0.44, 0.43, 0.4).mul(grain.sub(0.5).mul(0.2).add(1))
    .mul(float(1).sub(f01(fract(S.div(2)).lessThan(0.02)).mul(resolved(fwS, 0.5)).mul(0.3)));
  const railE = f01(A.greaterThan(-1.05).and(A.lessThan(-0.95))).mul(resolved(fwA, 10));
  const copingE = mix(copingC, vec3(0.12, 0.12, 0.12), railE.mul(0.6));
  let wallE = vec3(0.34, 0.335, 0.31).mul(streak.sub(0.5).mul(0.6).add(1));
  wallE = mix(wallE, vec3(0.06, 0.075, 0.045), smoothstep(0.7, 1.5, A.add(streak.sub(0.5).mul(0.5))));
  const embank = mix(wallE, copingE, b0);

  // --- pond bank: lawn and soil edge with boulders; stones and mud down to the water
  const lawn = mix(vec3(0.06, 0.085, 0.03), vec3(0.1, 0.12, 0.045), grain);
  const soilPatch = smoothstep(0.55, 0.75, stain);
  let edge = mix(lawn, vec3(0.13, 0.105, 0.075), soilPatch.mul(0.7).add(smoothstep(-0.8, 0, A).mul(0.5)).clamp(0, 1));
  // (city.json shores.pondBank, opt-in: { cell (m, 1.4), share (0.45), tone [[dark], [light]] linear, height (0.9) }:
  // the boulders' spacing, how many cells hold one, their colour range and relief. Singapore M5 fix round: the pale
  // 1.4 m boulders lit up to 1.8x read as white eggs along the Gardens' ponds; smaller, greyer, flatter granite)
  const PB = POND_BANK ?? {};
  const bCell = PB.cell ?? 1.4, bTone = PB.tone ?? [[0.33, 0.31, 0.27], [0.45, 0.43, 0.38]];
  const boulder = worley(AS.div(vec2(bCell, bCell)), 29);
  const bR = boulder.id.mul(0.3).add(0.3);
  const hasB = f01(hashI(floor(boulder.id.mul(7919)), float(3), 31).lessThan(PB.share ?? 0.45)).mul(resolved(fw.div(bCell), 3));
  const inB = below(bR.mul(bR).mul(0.8), bR.mul(bR), boulder.d2).mul(hasB);
  const bLit = bumpLight(boulder.off.div(bR).negate(), sun, PB.height ?? 0.9);
  const boulderC = mix(vec3(...bTone[0]), vec3(...bTone[1]), boulder.id).mul(bLit);
  edge = mix(edge, boulderC, inB);
  const pebbles = worley(AS.div(0.35), 37);
  let stones = mix(vec3(0.11, 0.1, 0.075), vec3(0.24, 0.22, 0.18), pebbles.id).mul(mix(float(1), float(0.55), smoothstep(0.1, 0.25, pebbles.d2).mul(resolved(fw, 3))));
  stones = mix(stones, boulderC, inB);
  stones = stones.mul(mix(float(1), float(0.55), smoothstep(0.4, 1.3, A)));          // wet towards the water
  const pond = mix(stones, edge, b0);

  // --- pond edge: granite coping in 1 m blocks, a short stone face darkening to the water
  const capBlock = hashI(floor(S), float(0), 79);
  const capJ = f01(fract(S).lessThan(0.03)).mul(resolved(fwS, 1));
  const capE = mix(vec3(0.42, 0.4, 0.36), vec3(0.5, 0.48, 0.44), capBlock).mul(grain.sub(0.5).mul(0.15).add(1)).mul(float(1).sub(capJ.mul(0.3)));
  const faceE = mix(vec3(0.16, 0.155, 0.14), vec3(0.05, 0.055, 0.04), smoothstep(0.1, 0.33, A));
  const pedge = mix(faceE, capE, b0);

  // --- quaywall (river quays: Paris's Seine): a pale limestone face in 0.5 m courses of staggered blocks,
  // dark and green at its wet foot (across = metres over the water on the face), and an apron of granite
  // setts with a stone coping along the edge (across = metres from the face, negative inland)
  const course = floor(A.div(0.5));
  const runS = S.div(1.1).add(course.mul(0.5));
  const qBlock = hashI(floor(runS), course, 83);
  const qJoint = max(f01(fract(A.div(0.5)).lessThan(0.06)), f01(fract(runS).lessThan(0.03))).mul(resolved(fw, 2));
  let ashlar = mix(vec3(0.46, 0.43, 0.37), vec3(0.58, 0.54, 0.46), qBlock).mul(stain.sub(0.5).mul(0.35).add(1))
    .mul(float(1).sub(qJoint.mul(0.35)));
  ashlar = mix(ashlar, vec3(0.09, 0.1, 0.075), below(0.15, 1.1, A.add(stain.sub(0.5).mul(0.5))));
  // (granite setts ~0.15 m in rows along the quay, grey-beige; 0.6 m cells of strong contrast read as a pixel
  // mosaic from the bridges, Paris M4): each sett's tone, faint joints, a patch tone per 3 m
  const settRow = floor(A.div(0.15));
  const sett = mix(float(0.5), hashI(floor(S.div(0.15).add(settRow.mul(0.5))), settRow, 89), resolved(fw, 6.7));
  const settJ = f01(fract(A.div(0.15)).lessThan(0.12)).mul(resolved(fw, 13));
  const setts = mix(vec3(0.34, 0.33, 0.31), vec3(0.4, 0.39, 0.36), sett).mul(float(1).sub(settJ.mul(0.25)))
    .mul(hashI(floor(S.div(3)), floor(A.div(3)), 91).mul(0.06).add(0.97)).mul(stain.sub(0.5).mul(0.25).add(1));
  const qCoping = vec3(0.58, 0.55, 0.48).mul(grain.sub(0.5).mul(0.15).add(1))
    .mul(float(1).sub(f01(fract(S.div(1.4)).lessThan(0.03)).mul(resolved(fwS, 0.7)).mul(0.3)));
  // (city.json shores.quayGrass {paved, share}: inland of a `paved` m band of setts behind the coping the apron is
  // a rough lawn, its edge wobbled (Berlin M5 critic: the Landwehrkanal's walls with an empty paved shelf); off by default)
  let apronTop = setts;
  if (QUAY_GRASS) {
    const lawnN = fbm(AS.div(5), fw.div(5), 2, 97);
    const lawnC = mix(vec3(0.06, 0.075, 0.035), vec3(0.11, 0.12, 0.06), lawnN);
    const edge = A.add(float(QUAY_GRASS.paved ?? 2.5)).add(fbm(AS.div(vec2(3, 6)), fw.div(3), 2, 99).sub(0.5).mul(0.8));
    apronTop = mix(setts, lawnC, below(-0.15, 0.15, edge).mul(QUAY_GRASS.share ?? 1));
  }
  const quayWall = mix(ashlar, mix(apronTop, qCoping, f01(A.greaterThan(-0.7))), b0);

  // --- pool coping
  const poolC = vec3(0.58, 0.57, 0.54).mul(grain.sub(0.5).mul(0.15).add(1));

  const col = revet.mul(is(TYPE.revetment)).add(quay.mul(is(TYPE.quay))).add(beach.mul(is(TYPE.beach)))
    .add(mud.mul(is(TYPE.mudflat))).add(embank.mul(is(TYPE.embankment))).add(pond.mul(is(TYPE.pondbank)))
    .add(poolC.mul(is(TYPE.pool))).add(pedge.mul(is(TYPE.pondedge))).add(quayWall.mul(is(TYPE.quaywall)));
  m.colorNode = col;
  // wet surfaces are glossier
  const wetness = is(TYPE.revetment).mul(b1).mul(wet).add(is(TYPE.beach).mul(b1)).add(is(TYPE.mudflat).mul(b1))
    .add(is(TYPE.quay).mul(b1).mul(below(0.3, 0.55, h))).clamp(0, 1);
  m.roughnessNode = mix(float(0.92), float(0.45), wetness);
  m.userData.nodes = { type, band, A, S };
  return m;
}

// ---------------------------------------------------------------- blended toe bands over the water
function shallowsMaterial(sunDir) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.35, metalness: 0, transparent: true, depthWrite: false });
  const sun = uniform(sunDir);                     // live: follows the time of day
  const stain = fbm(AS.div(vec2(3, 9)), fw.div(3), 3, 5);
  const wob = fbm(AS.div(vec2(2, 6)), fw.div(2), 2, 41);

  // revetment toe: submerged rocks seen through turbid water, a thin wet lapping line at the top
  const t = A.sub(5).div(8).clamp(0, 1);
  const rock = worley(AS.div(0.9), 11);
  const rockMask = below(0.35, 0.6, rock.d2).mul(resolved(fw.div(0.9), 3)).mul(0.5).add(0.5);
  const toeCol = mix(vec3(0.07, 0.075, 0.05), vec3(0.1, 0.1, 0.075), rock.id);
  const toeA = pow15(float(1).sub(t)).mul(0.75).mul(rockMask.mul(0.6).add(0.4)).mul(below(0.7, 1, t.add(wob.sub(0.5).mul(0.4))));
  const lap = below(0.02, 0.1, t.add(wob.sub(0.5).mul(0.06)));
  const revCol = mix(toeCol, vec3(0.35, 0.36, 0.33), lap.mul(0.35));
  const revA = max(toeA, lap.mul(0.5));

  // quay: the wall's shadow and dark reflection on the water right below it
  const tq = A.div(4).clamp(0, 1);
  const quayA = pow15(float(1).sub(tq)).mul(0.55);
  const quayCol = vec3(0.025, 0.028, 0.025);

  // beach: swash lines of foam over shallow sandy water
  const tb = A.sub(14).div(12).clamp(0, 1);
  const foamLine = (c, w) => below(float(0), float(w), abs(tb.sub(c).add(wob.sub(0.5).mul(0.08))))
    .mul(smoothstep(0.35, 0.6, vnoise(AS.div(vec2(1.5, 4)), 43)));
  const foam = max(foamLine(0.04, 0.03), foamLine(0.2, 0.02).mul(0.7));
  const beachCol = mix(vec3(0.24, 0.22, 0.17), vec3(0.62, 0.62, 0.6), foam);
  const beachA = max(pow15(float(1).sub(tb)).mul(0.55), foam.mul(0.85));

  // mudflat: exposed mud in lobes and ridges between drainage channels running out to sea, the wet mud
  // glistening; it frays into the sea further out
  const tm = A.sub(4).div(66).clamp(0, 1);
  const lobes = fbm(AS.div(vec2(22, 30)), fw.div(22), 3, 47);
  const channels = abs(sin(S.div(26).add(fbm(AS.div(vec2(14, 40)), fw.div(14), 2, 53).mul(5)))).mul(0.8)
    .add(abs(sin(S.div(9).add(A.div(7)).add(wob.mul(4)))).mul(0.2));
  // the outer limit wanders (bars and bays of mud, tens of metres), so the fringe never runs parallel
  // to the edge it grows from
  const reachM = fbm(vec2(S.div(90), A.div(40)), fwS.div(90), 3, 49);
  const tmw = tm.add(reachM.sub(0.5).mul(0.7));
  const exposed = smoothstep(tmw.mul(0.8).add(0.3), tmw.mul(0.8).add(0.42), lobes.mul(0.6).add(channels.mul(0.4)));
  // wet mud at the water's edge: darker than the drier flat behind it, and glossy
  const mudCol = mix(vec3(0.085, 0.078, 0.062), vec3(0.11, 0.1, 0.078), stain);
  const mudA = exposed.mul(0.9).add(below(0.0, 0.25, tmw).mul(0.2).mul(float(1).sub(exposed))).clamp(0, 1);

  // embankment foot: wet stain and shadow
  const te = A.sub(1.6).div(2.9).clamp(0, 1);
  const embA = pow15(float(1).sub(te)).mul(0.5);
  const embCol = vec3(0.025, 0.035, 0.022);
  // pond edge: a narrow dark band where the stone face meets the water
  const tpe = A.sub(0.35).div(2.65).clamp(0, 1);
  const pedgeA = pow15(float(1).sub(tpe)).mul(0.45);

  // pond shallows: the muddy bottom showing near the bank, stones, and lily pads in patches
  const tp = A.sub(1.4).div(3.6).clamp(0, 1);
  const pebble = worley(AS.div(0.45), 59);
  const bottom = mix(vec3(0.07, 0.07, 0.045), vec3(0.12, 0.11, 0.08), pebble.id.mul(below(0.1, 0.2, pebble.d2)).mul(resolved(fw, 2)));
  const pads = worley(AS.div(0.7), 61);
  const padR = pads.id.mul(0.15).add(0.25);
  const patch = smoothstep(0.62, 0.72, fbm(AS.div(vec2(6, 11)), fw.div(6), 2, 67).add(below(0, 0.5, tp).mul(0.1)));
  const pad = below(padR.mul(padR).mul(0.8), padR.mul(padR), pads.d2).mul(patch).mul(resolved(fw.div(0.7), 3));
  const padCol = mix(vec3(0.05, 0.1, 0.025), vec3(0.09, 0.14, 0.04), pads.id).mul(bumpFlat(sun));
  const pondCol = mix(bottom, padCol, pad);
  const pondA = max(pow15(float(1).sub(tp)).mul(0.6), pad);

  const col = revCol.mul(is(TYPE.revetment)).add(quayCol.mul(is(TYPE.quay))).add(beachCol.mul(is(TYPE.beach)))
    .add(mudCol.mul(is(TYPE.mudflat))).add(embCol.mul(is(TYPE.embankment))).add(pondCol.mul(is(TYPE.pondbank)))
    .add(embCol.mul(is(TYPE.pondedge)));
  const alpha = revA.mul(is(TYPE.revetment)).add(quayA.mul(is(TYPE.quay))).add(beachA.mul(is(TYPE.beach)))
    .add(mudA.mul(is(TYPE.mudflat))).add(embA.mul(is(TYPE.embankment))).add(pondA.mul(is(TYPE.pondbank)))
    .add(pedgeA.mul(is(TYPE.pondedge)));
  m.colorNode = col;
  m.opacityNode = alpha.clamp(0, 1);
  // mud and foam are matte-ish, wet mud glossy; the water-coloured veils as glossy as the water
  m.roughnessNode = mix(float(0.3), float(0.6), is(TYPE.beach).mul(foam));
  return m;
}
const pow15 = (x) => x.mul(x.sqrt());
// flat things lying on the water (lily pads) are lit like flat ground whatever the band's normal
const bumpFlat = (sun) => float(1);

// ---------------------------------------------------------------- pools
// pool (city.json shores.pool, default the turquoise below): {shallow, deep} linear rgb (Berlin's Prinzenbad read as neon
// cyan from the Kreuzberg view: a greyer, darker blue-green)
function poolMaterial(pool = null) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.08, metalness: 0 });
  const P = positionWorld.xz;
  const fwP = max(fwidth(P.x), fwidth(P.y));
  // turquoise over white tiles, darker where the water is deeper (towards the middle, from noise),
  // with a lane-line hint and soft caustic ripples
  const deep = fbm(P.div(9), fwP.div(9), 2, 71);
  const caustic = mix(float(0.5), vnoise(P.div(0.6), 73), resolved(fwP.div(0.6)));
  m.colorNode = mix(vec3(...(pool?.shallow ?? [0.08, 0.35, 0.4])), vec3(...(pool?.deep ?? [0.03, 0.2, 0.28])), deep).mul(caustic.mul(0.25).add(0.88));
  m.userData.water = true;
  return m;
}

let QUAY_GRASS = null;          // (city.json shores.quayGrass: see the quaywall)
let POND_BANK = null;           // (city.json shores.pondBank: see the pond bank)
// Load shores/shores.glb (05e_shores.py); resolves to the group added to the scene, or null if missing.
export async function loadShores(loader, base, { sunDir, pool = null, quayGrass = null, pondBank = null }) {
  QUAY_GRASS = quayGrass;
  POND_BANK = pondBank;
  const index = await fetch(base + 'shores.json', { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (!index) return null;
  const gltf = await loader.loadAsync(base + index.file);
  const mats = { shore: shoreMaterial(sunDir), shallows: shallowsMaterial(sunDir), pools: poolMaterial(pool) };
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    const name = o.material?.name;
    o.material = mats[name] ?? mats.shore;
    o.receiveShadow = true;
    o.castShadow = false;
    o.userData.noReflect = true;            // flat and at the water line: nothing to see in the mirror
    o.frustumCulled = false;
    if (name === 'shallows') { o.renderOrder = 1; o.userData.overWater = true; }   // (main.js ANIM_OVERLAY_WATER)
  });
  gltf.scene.userData.materials = mats;
  return gltf.scene;
}
