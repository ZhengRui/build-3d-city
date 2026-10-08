// The town beyond the districts as block masses (06e_masses.py, [ground] masses): flat-roofed shells of the OSM
// footprints, merged per block and height class, seen from hundreds of metres to kilometres away. One cheap
// material, shaded flat (the shells share their vertices between roof and walls and carry no normals): the
// vertex colour is the wall's (render, stone, brick, concrete), its alpha the roof's kind (zinc, slate,
// terracotta, gravel...); the walls get storeys and windows, box-filtered so that from far they are the wall's
// tone a little darkened, as a facade full of windows is.
import * as THREE from 'three/webgpu';
import { float, vec2, vec3, vertexColor, positionWorld, fwidth, floor, mod, min, max, clamp, mix, abs,
  hash, dot, select, dFdx, dFdy, cross, normalize, round, smoothstep } from 'three/tsl';

// box-filtered stripes: the share of the pixel's footprint covered by pulses of width w every `period`
function pulses(x, period, width, fw) {
  const Pn = float(period), w = float(width);
  const F = (t) => floor(t.div(Pn)).mul(w).add(min(mod(t, Pn), w));
  const s = x.add(w.mul(0.5));
  const fwc = max(fw, 1e-4);
  return clamp(F(s.add(fwc.mul(0.5))).sub(F(s.sub(fwc.mul(0.5)))).div(fwc), 0, 1);
}

// roof kinds (06e_masses.py ROOF_KINDS), linear RGB: gravel, membrane, pale coating, zinc, slate, terracotta
const ROOFS = [[0.2, 0.19, 0.175], [0.06, 0.06, 0.06], [0.33, 0.33, 0.31], [0.15, 0.165, 0.18], [0.075, 0.08, 0.09],
  [0.2, 0.085, 0.055]];

// opts (city.json masses): roofTint, wallTint (linear rgb multipliers on the roofs' and walls' colours, default none)
// and weathered (the share of terracotta roofs weathered to brown-grey, default 0.5), to bring the ring's tone to the
// districts' own beside it (Berlin M3 fix round: a brown-red ring round pale districts drew their outline)
// a colour from [[r, g, b, weight], ...] (sRGB 0..1) picked by weight with the hash id (0..1), ±spread/2 in brightness (linear rgb)
function pickPalette(palette, id, spread) {
  const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const total = palette.reduce((a, p) => a + (p[3] ?? 1), 0);
  let acc = 0, pick = vec3(lin(palette[0][0]), lin(palette[0][1]), lin(palette[0][2]));
  for (let i = 0; i < palette.length - 1; i++) {
    acc += (palette[i][3] ?? 1) / total;
    const next = palette[i + 1];
    pick = select(id.greaterThan(acc), vec3(lin(next[0]), lin(next[1]), lin(next[2])), pick);
  }
  return pick.mul(hash(id.mul(17.3)).mul(spread).add(1 - spread / 2));
}

export function createMassesMaterial(night = null, opts = {}) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.85, metalness: 0 });
  m.flatShading = true;
  const vc = vertexColor();
  const n = normalize(cross(dFdx(positionWorld), dFdy(positionWorld)));
  const roof = smoothstep(0.6, 0.8, abs(n.y));                 // 1 on roofs, 0 on walls
  // (half the terracotta roofs weathered to brown-grey: the M7 overview read them as orange confetti)
  const k0 = round(vc.a.mul(8));
  const kind = select(k0.equal(5).and(hash(floor(vc.g.mul(733))).lessThan(opts.weathered ?? 0.5)), float(4), k0);
  let roofCol = vec3(...ROOFS[0]);
  for (let k = 1; k < ROOFS.length; k++) roofCol = select(kind.equal(k), vec3(...ROOFS[k]), roofCol);
  roofCol = roofCol.mul(hash(floor(vc.r.mul(997)).add(floor(vc.g.mul(577)))).mul(0.25).add(0.88));
  if (opts.roofTint) roofCol = roofCol.mul(vec3(...opts.roofTint));
  // (opts.roofPalette, default none (Tokyo M8): [[r, g, b, weight], ...] sRGB roof colours that replace the roof kinds' (and
  // roofTint) per mass, picked by weight from a hash of the mass's own colour, each ±8 % in brightness: grey concrete, blue-grey
  // and slate, corrugated metal and some brown, not the European kinds' terracotta)
  if (opts.roofPalette) roofCol = pickPalette(opts.roofPalette, hash(floor(vc.r.mul(613)).add(floor(vc.g.mul(907))).add(floor(vc.b.mul(271)).mul(13))), 0.16);
  // along the wall: world xz projected on the wall's direction
  const u = dot(positionWorld.xz, normalize(vec2(n.z.negate(), n.x).add(1e-5)));
  const y = positionWorld.y;
  const fu = max(fwidth(u), 1e-4), fy = max(fwidth(y), 1e-4);
  // windows 1.3 x 1.7 m in bays of 2.9 m and storeys of 3.1 m
  const win = pulses(u, 2.9, 1.3, fu).mul(pulses(y.add(0.9), 3.1, 1.7, fy));
  const bay = floor(u.div(2.9)).add(floor(y.div(3.1)).mul(131));
  // (opts.windowVary, default 1 (Tokyo M8): the spread of the window panes' tones about their mean; under 1 the ring's walls
  // lose the dark speckle of random black panes seen from a few hundred metres)
  const glass = opts.windowVary != null ? mix(vec3(0.035, 0.04, 0.045), vec3(0.11, 0.115, 0.12), hash(bay.add(7)).sub(0.5).mul(opts.windowVary).add(0.5))
    : mix(vec3(0.035, 0.04, 0.045), vec3(0.11, 0.115, 0.12), hash(bay.add(7)));
  let wallBase = opts.wallTint ? vc.rgb.mul(vec3(...opts.wallTint)) : vc.rgb;
  // (opts.palette, default none (Singapore M8): [[r, g, b, weight], ...] sRGB wall colours that replace the pipeline's
  // (06e_masses' European render, stone and brick) per mass, picked by weight from a hash of the mass's own colour:
  // the far HDB towns white and cream with a few pastels, not tan and brown; each mass ±6 % in brightness)
  if (opts.palette) {
    const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    const total = opts.palette.reduce((a, p) => a + (p[3] ?? 1), 0);
    const id = hash(floor(vc.r.mul(991)).add(floor(vc.g.mul(587))).add(floor(vc.b.mul(389)).mul(7)));
    let acc = 0, pick = vec3(lin(opts.palette[0][0]), lin(opts.palette[0][1]), lin(opts.palette[0][2]));
    for (const p of opts.palette.slice(0, -1)) {
      acc += (p[3] ?? 1) / total;
      const next = opts.palette[opts.palette.indexOf(p) + 1];
      pick = select(id.greaterThan(acc), vec3(lin(next[0]), lin(next[1]), lin(next[2])), pick);
    }
    wallBase = pick.mul(hash(id.mul(17.3)).mul(0.12).add(0.94));
  }
  // (opts.cellTint, 0..1, default 0: the walls tinted per mass and per 400 m cell among ochre, grey, pink, buff and
  // darker render, so the ring is not one beige (Berlin M7 fix round))
  if (opts.cellTint) {
    const TINTS = [[1, 1, 1], [1.1, 0.98, 0.84], [0.88, 0.92, 0.98], [1.08, 0.9, 0.82], [0.8, 0.79, 0.77], [1.02, 1.0, 0.93]];
    const cellH = hash(floor(positionWorld.x.div(400)).add(floor(positionWorld.z.div(400)).mul(311)).add(floor(vc.r.mul(997))));
    const ti = floor(cellH.mul(TINTS.length));
    let tint = vec3(...TINTS[0]);
    for (let k = 1; k < TINTS.length; k++) tint = select(ti.equal(k), vec3(...TINTS[k]), tint);
    wallBase = wallBase.mul(mix(vec3(1), tint, opts.cellTint));
  }
  // (opts.farWindows, default 1: the windows' contrast where they shrink towards a pixel, times this: the dense dark
  // window noise of the ring seen from a few kilometres)
  const winK = opts.farWindows != null
    ? mix(float(0.85), float(0.85 * opts.farWindows), smoothstep(0.05, 0.35, max(fu.div(2.9), fy.div(3.1)))) : float(0.85);
  const wall = mix(wallBase, glass, win.mul(winK));
  m.colorNode = mix(wall, roofCol, roof);
  m.roughnessNode = mix(mix(float(0.85), float(0.35), win), float(0.8), roof);
  // after dark: a share of the windows lit, warm, dimmer and sparser than Paris's own blocks (the M7 critic:
  // the banlieue glowed brighter and whiter than Paris), about half the home share of the hour; where the
  // windows get smaller than a pixel their mean (a hash per sub-pixel window sparkled as confetti), and the
  // walls a little darker than by day, so the far masses stay a dim, patchy sheet under the city's
  if (night) {
    const share = night.home ? night.home.mul(0.3) : float(0.12);
    const res = float(1).sub(smoothstep(0.35, 0.9, max(fu.div(2.9), fy.div(3.1))));
    const lit = mix(share, select(hash(bay.add(17)).lessThan(share), float(1), float(0)), res);
    let lamp = mix(vec3(1.0, 0.5, 0.17), vec3(1.0, 0.66, 0.34), hash(bay.add(29)));
    let emission = lamp.mul(win.mul(lit).mul(float(1).sub(roof)).mul(0.5));
    // (night.masses { k, white, patch } (London M8 fix round; null: as before): their mean windows times k, the lamps
    // whitened by `white` (0..1: an orange mean read as an amber carpet over the town ring), and once the windows are
    // a pixel or less, patch: 50 m cells of the town lit unevenly (0..1), so the ring reads as clusters of lights
    // on a dark town, not an even glow)
    // (Singapore M8 fix round 1, both optional: lamp, the whitened lamps' colour instead of [1, 0.78, 0.55] (linear: the
    // far HDB towns' white LED, not a warm haze); corridors, a lit band under each storey's ceiling on that share of the
    // masses (the HDB slabs' open corridors, lit all night), box-filtered: lines close up, an even glow far off)
    const MS = night.masses;
    if (MS) {
      lamp = mix(lamp, MS.lamp ? vec3(...MS.lamp) : vec3(1, 0.78, 0.55), MS.white ?? 0);
      const cell = hash(floor(positionWorld.x.div(50)).add(floor(positionWorld.z.div(50)).mul(1847)));
      const patchy = mix(float(1), cell.mul(cell).mul(3), float(1).sub(res).mul(MS.patch ?? 0));
      emission = lamp.mul(win.mul(lit).mul(float(1).sub(roof)).mul(0.5 * (MS.k ?? 1))).mul(patchy);
      // (far, default none (Tokyo M8 fix round 1): the windows' mean times that once they are under a pixel (res 0), so the
      // ring seen from the overview and the observatories is a carpet of lights, not a dim brown band)
      if (MS.far != null) emission = emission.mul(mix(float(MS.far), float(1), res));
      if (MS.corridors) {
        const [share, k] = MS.corridors;
        const has = select(hash(floor(vc.r.mul(991)).add(floor(vc.b.mul(389)).mul(13)).add(5)).lessThan(share), float(1), float(0));
        const band = pulses(y.add(0.45), 3.1, 0.45, fy);
        emission = emission.add(lamp.mul(band.mul(has).mul(float(1).sub(roof)).mul(k)));
      }
    }
    night.withNight(m, (litMat) => {
      // (night.masses.dusk: the walls darken only as the night deepens (the city glow's share, night.js), not from the
      // first twilight: at dusk the ring was 2.4 times darker than the districts beside it, a step along the boundary;
      // Berlin M8 fix round)
      // (night.masses.walls, default 0.55 (Hong Kong M8 critic 2: the margin's pale estates read as daylit grey-white
      // blocks under the night fill, the brightest far objects): the walls' factor after dark)
      const wk = float(MS?.walls ?? 0.55);
      litMat.colorNode = MS?.dusk ? m.colorNode.mul(mix(float(1), wk, night.cityGlow)) : m.colorNode.mul(wk);
      litMat.emissiveNode = emission.mul(night.lights);
    });
  }
  return m;
}
