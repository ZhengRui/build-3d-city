// Ground, road and road-marking materials (TSL); main.js loads the markings tiles (06b_markings.py).
//
// Everything is procedural in world or road coordinates, no textures:
//   land      urban ground: parcels of paving, concrete, worn asphalt, bare laterite soil and scrub,
//             with slab joints and stains; scrub and woods where it is steep or high up (the hills)
//   town      built-up land beyond the districts, where no buildings are modelled (06_tiles.py's town
//             layer, [ground] town): a painted roofscape of blocks, lots and streets seen from above, which
//             the backdrop's towns carry on beyond the ground area's edge
//   green     parks and woodland: individual tree crowns (Worley cells) shaded as domes lit from the sun's
//             side, with their shadows, over lawn in open parks and dark understory in closed woodland
//   aeroway   concrete apron and taxiway panels along the runway heading, joints, rubber and oil stains
//   road      the merged road polygons of 06_tiles.py (vertex colour by road class): asphalt grain,
//             repaving patches; railways get ballast
//   markings  strips laid over the roads with (across, along) coordinates: lane and edge lines, the
//             yellow centre line, zebra crossings and stop lines, sidewalks with kerbs, tree pits,
//             tactile paving and bike lanes, planted medians, runways, pedestrian streets
// What differs between cities comes from city.json (createGroundMaterials' options): the runway heading, the
// lawn's colour, the share of sodium street lamps, the centre lines' colour and the dash lengths.
// Detail is filtered by its size on screen (fwidth): each noise octave fades to its mean once its cells
// get smaller than a pixel and lines are box-filtered, so distant ground averages out instead of
// shimmering. The road material and the markings' asphalt share one function of world position, so
// they meet without a seam.
//
// After dark (the uniforms from night.js, in the materials' lit copies) the streets are lit: on the markings, pools of light under lamp
// posts along both kerbs of every carriageway (warm sodium on expressways and some districts' arterials,
// white LED elsewhere), which average out to their mean when the posts get closer than a few pixels, and
// the lamp heads' own glow once a road is a line a few pixels wide, so from far above the network reads as
// glowing lines; runway edge and centre lights; the road mesh at junctions and bridge decks at the mean;
// scattered courtyard lamps on urban land, fewer in parks, floodlit aprons at the airport. The light is
// added as emission: the surface's own colour times the light falling on it.
//
// Branchless style as in facade.js: TSL turns a select between two heavy branches into an if/else and
// nodes first built inside one branch are then undefined in the other, so choices are mixes with 0/1
// weights (`sel`) and every node is evaluated at the top level.
import * as THREE from 'three/webgpu';
import {
  float, vec2, vec3, uint, uv, vertexColor, positionWorld, normalWorld, fwidth, hash,
  select, mix, smoothstep, clamp, max, min, abs, floor, fract, mod, dot, pow,
  uniform, cameraPosition, distance, exp, normalWorldGeometry, sin, cos, dFdx, dFdy, cross, normalize, texture, Fn, If,
  textureLoad, ivec2,
} from 'three/tsl';

const f01 = (c) => select(c, float(1), float(0));
const sel = (c, a, b) => mix(b, a, f01(c));
// 1 below lo, 0 above hi (smoothstep with reversed edges is undefined in GLSL and WGSL)
const below = (lo, hi, x) => float(1).sub(smoothstep(lo, hi, x));

// ---------------------------------------------------------------- noise
// Integer lattice hash: cell coordinates (possibly negative, up to a few 100k) wrapped to 16 bits and
// mixed as unsigned integers, so large world coordinates don't lose precision in a float seed.
const OFF = 65536 * 16;
const hashI = (ix, iz, salt = 0) => hash(
  mod(ix.add(OFF), 65536).toUint().mul(uint(0x9E3779B1))
    .bitXor(mod(iz.add(OFF), 65536).toUint().mul(uint(0x85EBCA77)))
    .add(uint(salt * 0x27D4EB2F >>> 0)));
const hash2 = (p, salt = 0) => hashI(p.x, p.y, salt);

// value noise in 0..1 with smooth interpolation
function vnoise(p, salt = 0) {
  const i = floor(p), f = fract(p);
  const u = f.mul(f).mul(f.mul(-2).add(3));
  const a = hashI(i.x, i.y, salt), b = hashI(i.x.add(1), i.y, salt);
  const c = hashI(i.x, i.y.add(1), salt), d = hashI(i.x.add(1), i.y.add(1), salt);
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// how much of a feature of `cells` per unit is still resolved, given fw units per pixel: 1 sharp, 0 sub-pixel
const resolved = (fw, freq = 1) => float(1).sub(smoothstep(0.3, 0.9, fw.mul(freq)));

// fractal noise in 0..1, each octave faded to its mean (0.5) once it gets smaller than a pixel
function fbm(p, fw, octaves = 4, salt = 0) {
  let sum = float(0), norm = 0, amp = 1, f = 1;
  for (let i = 0; i < octaves; i++) {
    sum = sum.add(mix(float(0.5), vnoise(p.mul(f), salt + i * 101), resolved(fw, f)).mul(amp));
    norm += amp;
    amp *= 0.5;
    f *= 2.03;
  }
  return sum.div(norm);
}

// box-filtered stripes: the share of a pixel footprint [x - fw/2, x + fw/2] covered by pulses of width w
// centred on multiples of period P (exact antialiasing, and the right average once lines are sub-pixel)
function pulses(x, period, width, fw) {
  const Pn = float(period), w = float(width);
  const F = (t) => floor(t.div(Pn)).mul(w).add(min(mod(t, Pn), w));   // integral of the pulse train
  const s = x.add(w.mul(0.5));                                         // pulses centred, not starting, on k P
  const fwc = max(fw, 1e-4);
  return clamp(F(s.add(fwc.mul(0.5))).sub(F(s.sub(fwc.mul(0.5)))).div(fwc), 0, 1);
}
// one box-filtered line of width w centred on c
function line(x, c, w, fw) {
  const fwc = max(fw, 1e-4);
  const lo = max(x.sub(fwc.mul(0.5)), c.sub(w.mul(0.5)));
  const hi = min(x.add(fwc.mul(0.5)), c.add(w.mul(0.5)));
  return clamp(hi.sub(lo).div(fwc), 0, 1);
}
// box-filtered band [a, b]
const span = (x, a, b, fw) => line(x, a.add(b).mul(0.5), b.sub(a), fw);

// ---------------------------------------------------------------- shared surfaces
const P = positionWorld.xz;
const fwP = max(fwidth(P.x), fwidth(P.y));          // metres per pixel on the ground
// (the defaults of functions that also take copies of them, for branches)
const P0 = P, fwP0 = fwP;

let ASPHALT_MOTTLE = 1;
// asphalt brightness factor around 1: aggregate grain, wear and repaving patches, all in world space
function asphaltFactor() {
  const big = fbm(P.div(55), fwP.div(55), 3, 11);                 // resurfacing, tens of metres
  const mid = fbm(P.div(5), fwP.div(5), 3, 23);                   // oil and wear blotches
  const blot = fbm(P.div(1.4), fwP.div(1.4), 2, 29);                // tar, fines, small repairs
  const grain = mix(float(0.5), vnoise(P.div(0.09), 37), resolved(fwP.div(0.09)));
  // (city.json ground.asphaltMottle: the resurfacing and wear blotches' strength, 1 by default; Berlin 0.5: the
  // junctions read as dark lakes of mottled asphalt, M5 critic)
  return float(1).add(big.sub(0.5).mul(0.34 * ASPHALT_MOTTLE)).add(mid.sub(0.5).mul(0.24 * ASPHALT_MOTTLE)).add(blot.sub(0.5).mul(0.16))
    .add(grain.sub(0.5).mul(0.34));
}

// ---------------------------------------------------------------- street lighting
// lamp colours (linear): high-pressure sodium, neutral and warm white LED
const SODIUM = vec3(1, 0.42, 0.1), LED = vec3(1, 0.86, 0.7), WARM_LED = vec3(1, 0.7, 0.42);
const LAMP_H = 10;                    // metres: mounting height of street lamps
// light on the ground from one lamp at horizontal distance r (squared), 1 right under it
const lampAt = (r2, h = LAMP_H) => float(h * h).div(r2.add(h * h)).pow(1.5);
// the lamps of one kerb: posts every `period` m along, `dx` m across from here; the nearest two posts,
// or the mean along a row of posts (the integral of lampAt along the row, over the period) once they
// are closer than a few pixels (fwL: metres of `along` per pixel)
// (the same for lamps of mounting height h: ground.plazaLamps' low park and promenade lamps)
function lampRowH(dx, along, period, phase, fwL, h) {
  const dl = fract(along.div(period).add(phase)).sub(0.5).mul(period);
  const dx2 = dx.mul(dx);
  const near = lampAt(dx2.add(dl.mul(dl)), h).add(lampAt(dx2.add(period.sub(abs(dl)).pow(2)), h));
  const mean = float(2 * h ** 3).div(period.mul(dx2.add(h * h)));
  return mix(mean, near, resolved(fwL.div(period), 3));
}
function lampRow(dx, along, period, phase, fwL) {
  const dl = fract(along.div(period).add(phase)).sub(0.5).mul(period);
  const dx2 = dx.mul(dx);
  const near = lampAt(dx2.add(dl.mul(dl))).add(lampAt(dx2.add(period.sub(abs(dl)).pow(2))));
  const mean = float(2 * LAMP_H ** 3).div(period.mul(dx2.add(LAMP_H * LAMP_H)));
  return mix(mean, near, resolved(fwL.div(period), 3));
}
// the light of the whole city dims with the night's `lights`; a district's arterials have one kind of lamp
// (by 1.5 km cells), small streets mostly warm LED; sodium: the shares of cells with sodium lamps on their
// arterials and on their small streets
const regionLamp = (big, motorway, sodium) => {
  const cell = floor(P.div(1500));
  const sodiumArterial = f01(hashI(cell.x, cell.y, 171).lessThan(sodium.arterial));
  const sodiumStreet = f01(hashI(cell.x, cell.y, 173).lessThan(sodium.street));
  const arterial = mix(LED, SODIUM, sodiumArterial), street = mix(WARM_LED, SODIUM, sodiumStreet);
  // (sodium.motorway, default none: all sodium; Singapore M8 0: LTA's expressways lit by white LED, as its streets)
  const mw = sodium.motorway == null ? SODIUM : mix(LED, SODIUM, f01(hashI(cell.x, cell.y, 179).lessThan(sodium.motorway)));
  return mix(mix(street, arterial, big), mw, motorway);
};
// how bright a lit street is: the light falling on it (lampAt 1 right under a lamp) times this
let STREET = 2.2;                      // (city.json ground.streetLight)
// where the city's real lamps light the streets (lamps.js, a node 0..1 by world position), the procedural posts
// are left out: PROC() is the share of them that remains (1 without an inventory)
let REAL_LAMPS = null;
// city.json ground.outerLamps { gain, tint }: the procedural posts beyond the inventory (Paris: the banlieue's
// streets, which lit at the full rate glowed as wide pale bands brighter than Paris itself, M7 critic) dimmer
// and warmer; default none (as they were)
let OUTER_LAMPS = null;
// city.json ground.townLights { gain, base }: the night of the ground between the town masses (townMaterial): the
// strength of its street lighting, and its even glow under the posts' points (Paris M9)
const STREET_GLOW = { gain: uniform(0.12), base: uniform(0.08), far: uniform(0.004) };
let TOWN_LED = null;
// (ground.townLights.white [r, g, b] linear, default none (Singapore M8 fix round 1): the LED share's colour between the
// town masses instead of LED (a near-white: the HDB towns' white lamps, not a warm haze), and the backdrop towns' dots
// that share of them in it; farK, the backdrop towns' dots times that (default 1.6))
let TOWN_WHITE = null, TOWN_FAR_K = 1.6, TOWN_PAINTED_LIT = null;
// (ground.townLights.roads { rgb, tol, k, sodium, white }, default none (Tokyo M8 fix round 1): the backdrop's major roads (the
// outer cover map's painted roads, 06e_masses cover_outer_roads: sRGB rgb, matched within tol) lit after dark as a glowing
// line, k its strength (linear), a `sodium` share of 1.5 km cells orange, the rest white (default LED): from the air and
// the observatories the plain beyond the ring read as a black void with no arterials)
let TOWN_ROADS = null;
// (ground.lampHeads, default 0.35: the street lamps' heads' glare averaged over a road seen as a line a few pixels wide;
// Tokyo M8 fix round 1: from the overview the districts' streets read as a faint grey web)
let LAMP_HEADS = 0.35;
const PROC = () => {
  const share = REAL_LAMPS ? float(1).sub(REAL_LAMPS()) : float(1);
  return OUTER_LAMPS ? vec3(...OUTER_LAMPS.tint).mul(OUTER_LAMPS.gain).mul(share) : share;
};

// linear RGB of 06_tiles.py's ROAD_RGB, which the markings' asphalt must match
const ROAD_MAJOR0 = [0.10, 0.104, 0.112], ROAD_MINOR0 = [0.13, 0.13, 0.136];
let ROAD_MAJOR = vec3(...ROAD_MAJOR0), ROAD_MINOR = vec3(...ROAD_MINOR0);
// city.json ground.asphalt ([r, g, b] multiplier, default none): Paris's asphalt is paler and warmer
// (#7b7876-#918e8b in the IGN orthophoto) than Shenzhen's and New York's
let ASPHALT_K = null;
// city.json ground.junctionPools { cell, h } (default none; Hong Kong M8): the road mesh's junctions under lamps of
// height h on a jittered grid of cell m, pools about the junction's mean light instead of one even wash (a flat
// polygon of lamp colour at every crossing, the M4 critic's "orange blob" on Nathan Road)
let JUNCTION_POOLS = null;

// ---------------------------------------------------------------- materials

// urban (city.json ground.urban, all optional): the lots' linear colours (paving, concrete, beige, darkTop), the
// shares of scrubby and bare-soil lots, how strong the weeds at lot edges and the stains are (1 = Shenzhen's) and
// the slab joints' grid (m). Paris's squares and courtyards (the Louvre's Cour Napoléon, the Étoile, the
// Invalides) are pale stone: no scrub or soil lots, few weeds, faint stains, 1.2 m slabs
const URBAN = { paving: [0.33, 0.315, 0.29], concrete: [0.3, 0.3, 0.29], beige: [0.37, 0.345, 0.305], darkTop: [0.23, 0.23, 0.225],
  scrub: 0.04, soil: 0.02, weeds: 1, stain: 1, slab: 6 };
const LAND_FAR = { on: false, from: uniform(3000), to: uniform(6000) };
// city.json ground.rock (opt-in; default: rock from ~31 to ~44 degrees, as before): [from, to] degrees of the face's
// slope over which the ground turns to bare rock, or false for none. Hong Kong M3 critic: its wooded and grassed
// hillsides run at 30-45 degrees, and the per-face test painted the LiDAR TIN's 20-80 m facets there as pale rock
// triangles over the green
const ROCK = { on: true, cosFrom: 0.86, cosTo: 0.72 };
function landMaterial(night, urban = {}) {
  const U = { ...URBAN, ...urban };
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.93, metalness: 0 });
  // parcels: a grid warped by noise, so each lot (plaza, car park, courtyard, bare site) has its own
  // surface and irregular edges
  // (urban.cell, opt-in: the lots' size in m, 60 by default, the warp scaled with it; Singapore 22: big vacant sites read
  // as a few huge Voronoi-like patches of grey)
  const LC = U.cell ?? 60, LK = LC / 60;
  const warp = vec2(fbm(P.div(90 * LK), fwP.div(90 * LK), 2, 3), fbm(P.div(90 * LK).add(17.3), fwP.div(90 * LK), 2, 5)).sub(0.5).mul(45 * LK);
  const cellP = P.add(warp).div(LC);
  const lot = hash2(floor(cellP), 7);
  const lot2 = hash2(floor(cellP), 9);
  // lot surfaces (linear): mostly close shades of paving and concrete, now and then a car park, a scrubby
  // vacant lot or a bare laterite building site. Kept subtle: from the air strong contrasts read as camouflage
  const paving = vec3(...U.paving), concrete = vec3(...U.concrete), beige = vec3(...U.beige);
  const darkTop = vec3(...U.darkTop), soil = vec3(0.3, 0.22, 0.155), scrub = vec3(0.14, 0.16, 0.1);
  const tScrub = 1 - U.scrub - U.soil, tSoil = 1 - U.soil;
  let base = mix(paving, concrete, f01(lot.greaterThan(0.4)));
  base = mix(base, beige, f01(lot.greaterThan(0.7)));
  base = mix(base, darkTop, f01(lot.greaterThan(0.88)));
  base = mix(base, scrub, f01(lot.greaterThan(tScrub)));
  base = mix(base, soil, f01(lot.greaterThan(tSoil)));
  base = base.mul(lot2.mul(0.12).add(0.94));
  const isScrub = f01(lot.greaterThan(tScrub).and(lot.lessThan(tSoil)));
  // slab joints on paved lots (a U.slab m grid in the lot's own offset), paver texture, stains
  const SL = U.slab, jw = Math.min(0.12, SL * 0.02);
  const slab = max(pulses(P.x.add(lot2.mul(SL)), float(SL), float(jw), fwP), pulses(P.y.add(lot.mul(SL)), float(SL), float(jw), fwP));
  const pav = mix(float(0.5), hash2(floor(P.div(0.6)), 13), resolved(fwP.div(0.6)));
  const stain = fbm(P.div(9), fwP.div(9), 4, 17);
  const fine = fbm(P.div(1.3), fwP.div(1.3), 3, 19);
  // grass creeping in at lot edges and in random patches, so the city floor is not one hard surface
  const edge = float(1).sub(smoothstep(0.0, 0.08, min(min(fract(cellP.x), float(1).sub(fract(cellP.x))),
    min(fract(cellP.y), float(1).sub(fract(cellP.y))))));
  const weedy = smoothstep(0.72, 0.8, fbm(P.div(14), fwP.div(14), 3, 29).add(edge.mul(0.15)).add(fine.sub(0.5).mul(0.35)));
  let col = base.mul(float(1).sub(slab.mul(0.12).mul(float(1).sub(isScrub))))
    .mul(pav.sub(0.5).mul(0.1).add(1))
    .mul(stain.sub(0.5).mul(0.35 * U.stain).add(1))
    .mul(fine.sub(0.5).mul(0.25 * U.stain).add(1));
  col = mix(col, vec3(0.075, 0.09, 0.045).mul(fine.add(0.6)), weedy.mul(0.7 * U.weeds));
  // city.json ground.urban.coverLawn { share, lawn: [dark, light] linear, paths } (default off): the land no OSM green
  // covers turns to a dull mottled lawn where the land cover map (06e_masses' inner map, 10 m WorldCover at 20 m a
  // pixel) has grass or trees: the courtyards of the Plattenbau estates and the Altbau blocks, which open data maps as
  // nothing (Berlin M5 critic: untextured grey paving in every aerial); its edges broken by noise, a few worn buff
  // paths across; car parks, yards and squares (built-up in the map) keep the paving
  if (U.coverLawn) {
    // (in a branch taken only where the cover map is green: its noises cost nothing on the paved lots and streets)
    const CL = U.coverLawn;
    const cc = coverColour();
    const share = max(nearClass(cc, CLASS.grass, 0.09), nearClass(cc, CLASS.wood, 0.09).mul(CL.wood ?? 0.9)).mul(COVER.on).toVar();
    const [l0, l1] = CL.lawn ?? [[0.07, 0.085, 0.04], [0.12, 0.13, 0.068]];
    const pathK = CL.paths ?? 0;
    const base0 = col;
    col = Fn(() => {
      const c = base0.toVar();
      If(share.greaterThan(0.1), () => {
        const p = P.toVar(), fw = fwP.toVar(), cp = cellP.toVar(), l2 = lot2.toVar();
        const n = fbm(p.div(7), fw.div(7), 2, 63);
        const g = smoothstep(0.35, 0.65, share.add(n.sub(0.5).mul(0.6))).mul(CL.share ?? 1);
        let lawnC = mix(vec3(...l0), vec3(...l1), n).mul(mix(float(0.5), hash2(floor(p.div(0.8)), 65), resolved(fw.div(0.8))).mul(0.12).add(0.94));
        if (pathK) {
          const pth = max(pulses(cp.x.mul(60), float(60), float(2.2), fw), pulses(cp.y.mul(60).add(23), float(60), float(1.8), fw))
            .mul(f01(l2.lessThan(pathK)));
          lawnC = mix(lawnC, vec3(0.3, 0.27, 0.21), pth);
        }
        c.assign(mix(c, lawnC, g));
      });
      return c;
    })();
  }
  // hillsides: land that no green area covers but that is steep (over ~10 degrees) or high up (much of
  // Hong Kong's country parks, unmapped woods beyond the districts) is scrub and forest, not paving
  const wildN = fbm(P.div(60), fwP.div(60), 3, 31);
  const wild = max(smoothstep(0.012, 0.04, float(1).sub(normalWorld.y).add(wildN.sub(0.5).mul(0.02))),
    smoothstep(110, 240, positionWorld.y.add(wildN.sub(0.5).mul(80))));
  const woods = mix(vec3(0.028, 0.045, 0.022), vec3(0.065, 0.08, 0.036), fbm(P.div(35), fwP.div(35), 3, 37))
    .mul(fine.mul(0.4).add(0.8));
  const near = rockFace(mix(col, woods, wild));
  // city.json ground.landFarCover [from, to] (m from the camera; default off): far out the districts' land shows what the
  // town layer between the masses shows (calmTown over the land cover map: its trees, lawns and paving), fully from
  // `to` on, so from the overview the districts (whose own trees end at the trees' FAR) and the town ring round them
  // are one ground with no outline (Berlin M3 fix round: pale districts in a dark ring); evaluated only out there
  m.colorNode = LAND_FAR.on ? Fn(() => {
    const c = near.toVar();
    const k = smoothstep(LAND_FAR.from, LAND_FAR.to, positionWorld.distance(cameraPosition)).mul(COVER.on).toVar();
    If(k.greaterThan(0), () => { c.assign(mix(c, calmTown(coverColour()).mul(TOWN_NEAR_TINT), k)); });
    return c;
  })() : near;
  m.roughnessNode = mix(mix(float(0.92), float(0.97), isScrub), float(0.95), wild);
  m.userData.nodes = { lot, base, stain, wild };
  // no yard lamps on the wild hillsides
  // (lamps on paved lots, half of them; none on bare sites and scrub)
  if (night) night.withLights(m, col.mul(LIT_AREAS ? yardLamps(24, 0.25, 0.035, f01(lot.lessThan(0.88).and(hash2(floor(cellP), 11).lessThan(0.5)))).add(litAreas())
    : yardLamps(24, 0.25, 0.035, f01(lot.lessThan(0.88).and(hash2(floor(cellP), 11).lessThan(0.5)))))
    .mul(float(1).sub(wild)));
  return m;
}

// Town: what an aerial photo shows of a dense low-rise city: blocks between streets (a grid turned a different
// way in each 2.4 km cell, as neighbourhood grids are), rows of narrow lots whose flat roofs differ in tone
// (tar, grey membrane, silver coating, a few brown or red), parapet lines between them, a strip of back
// yards down the middle of each block, now and then a block under one big light roof (warehouses, schools,
// shops). All box-filtered, so from far it is a mean grey-brown with streets as faint lines. Over the last
// The backdrop's towns (backdropMaterial) carry on the same pattern, so the ground area's edge draws no line
// through a town.
// Rock faces: where the ground is steeper than about 35 degrees (the lidar terrain at 10 m averages the
// Palisades' vertical face to about 40) (the Palisades' diabase columns, the schist of
// Fort Tryon and Inwood Hill) it is bare rock, warm grey-brown with vertical joints, darker in the gullies,
// over whatever the layer would draw there (the woods on the talus and the cliff top stay)
function rockFace(col) {
  if (!ROCK.on) return col;
  // the face's own slope from the position's screen derivatives: the ground layers' normals point up
  const fn = normalize(cross(dFdx(positionWorld), dFdy(positionWorld)));
  const steep = smoothstep(float(ROCK.cosFrom), float(ROCK.cosTo), fn.y.abs());   // from ~31 to ~44 degrees (ground.rock)
  // (Paris M9: its two noises only where the ground is that steep, in a branch built from copies of its inputs
  // taken before it: every flat pixel of the land, the parks and the backdrop paid five octaves for nothing)
  return Fn(() => {
    const c = col.toVar(), k = steep.toVar(), p = P.toVar(), fw = fwP.toVar(), py = positionWorld.y.toVar();
    If(k.greaterThan(0), () => {
      const joints = fbm(vec2(p.x.add(p.y).div(3), py.div(40)), fw.div(3), 3, 53);
      const rock = mix(vec3(0.16, 0.14, 0.12), vec3(0.3, 0.27, 0.23), joints)
        .mul(fbm(p.div(25), fw.div(25), 2, 57).mul(0.4).add(0.8));
      c.assign(mix(c, rock, k));
    });
    return c;
  })();
}
function townPattern(P = P0, fwP = fwP0) {
  const cell = floor(P.div(2400));
  const ang = hash2(cell, 301).mul(Math.PI / 2);
  const c = cos(ang), s = sin(ang);
  const Q = vec2(P.x.mul(c).sub(P.y.mul(s)), P.x.mul(s).add(P.y.mul(c))).add(vec2(hash2(cell, 302), hash2(cell, 304)).mul(200));
  const BX = 190, BZ = 80, ST = 17;                                   // block pitch along and across, street width
  const street = max(pulses(Q.x, BX, ST, fwP), pulses(Q.y, BZ, ST, fwP));
  const block = floor(Q.div(vec2(BX, BZ)));
  const big = f01(hash2(block, 305).lessThan(0.07));
  // two rows of lots back to back, 5.5-9 m wide
  const across = mod(Q.y, BZ);
  const row = f01(across.greaterThan(BZ / 2));
  const lotW = mix(float(5.5), float(9), hash2(block, 307));
  const lotI = floor(Q.x.div(lotW));
  const h = hashI(lotI, block.y.mul(2).add(row), 309);
  const tar = vec3(0.09, 0.09, 0.09), membrane = vec3(0.21, 0.21, 0.2), silver = vec3(0.36, 0.36, 0.35);
  const brown = vec3(0.2, 0.13, 0.09), bigRoof = vec3(0.3, 0.295, 0.28);
  let roof = mix(membrane, tar, f01(h.lessThan(0.3)));
  roof = mix(roof, silver, f01(h.greaterThan(0.72)));
  roof = mix(roof, brown, f01(h.greaterThan(0.93)));
  roof = mix(roof, vec3(0.2, 0.2, 0.19), resolved(fwP.div(lotW)).oneMinus());        // lots below a pixel: their mean
  roof = roof.mul(hashI(lotI, block.y, 311).mul(0.2).add(0.9));
  const parapet = pulses(Q.x, lotW, float(0.45), fwP);
  roof = mix(roof, vec3(0.16, 0.155, 0.15), parapet.mul(0.6));
  // back yards: a strip down the middle of the block, some trees, some paved
  // (New York's back yards are mostly under trees: from the air a green seam down each block)
  const yard = span(across, float(BZ / 2 - 9), float(BZ / 2 + 9), fwP);
  const yardCol = mix(vec3(0.04, 0.062, 0.03), vec3(0.16, 0.155, 0.14), smoothstep(0.55, 0.8, fbm(Q.div(9), fwP.div(9), 2, 313)));
  let col = mix(roof, yardCol, yard);
  col = mix(col, bigRoof.mul(fbm(Q.div(30), fwP.div(30), 2, 315).mul(0.2).add(0.9)), big);
  // streets: asphalt with a pale sidewalk edge and a row of street trees now and then
  const trees = f01(hash2(floor(Q.div(60)), 317).lessThan(0.65)).mul(0.7);
  col = mix(col, mix(ROAD_MINOR, vec3(0.05, 0.07, 0.035), trees), street);
  // large-scale mottling: neighbourhoods differ
  col = col.mul(fbm(P.div(700), fwP.div(700), 2, 319).sub(0.5).mul(0.3).add(1));
  return { col, street, rough: mix(float(0.88), float(0.7), f01(h.greaterThan(0.72)).mul(float(1).sub(street))) };
}
// ---------------------------------------------------------------- land cover (06e_masses: ESA WorldCover)
// Two colour maps: the whole backdrop at 50 m a pixel and the masses' zone at 20 m (tiles.json cover, its
// inner). Shared by the backdrop and the town layer (whose gardens and trees between the masses it places);
// setCover (main.js, after the first frame) switches them on
const COVER = { on: uniform(0), rect: uniform(new THREE.Vector4(0, 0, 1, 1)), innerRect: uniform(new THREE.Vector4(0, 0, 1, 1)),
  innerOn: uniform(0) };
// (scene z grows southwards; the maps' first row, their north edge z0, is v = 1 as loaded)
const coverUV = (r) => vec2(P.x.sub(r.x).div(r.z.sub(r.x)), r.w.sub(P.y).div(r.w.sub(r.y)));
COVER.outer = texture(new THREE.Texture(), coverUV(COVER.rect));
COVER.inner = texture(new THREE.Texture(), coverUV(COVER.innerRect));
// linear colours of the classes (06e_masses COVER_RGB, sRGB there)
const s2l = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const CLASS = Object.fromEntries(Object.entries({ wood: [50, 66, 40], grass: [98, 110, 72], field: [126, 120, 92], water: [40, 52, 44] })
  .map(([k, c]) => [k, vec3(...c.map((v) => s2l(v / 255)))]));
// the cover's colour here: the inner map inside its rectangle (faded over its last 400 m), the outer beyond
// (city.json ground.coverBlend, opt-in, Tokyo M7 fix round: the metres over which the inner map gives way to the outer
// at its edge, default 400: from the overview Tokyo's 10 m roofscape ended on a visible line against the 60 m map)
let COVER_BLEND = 400;
function coverColour() {
  const r = COVER.innerRect;
  const edge = min(min(P.x.sub(r.x), r.z.sub(P.x)), min(P.y.sub(r.y), r.w.sub(P.y)));
  const w = smoothstep(float(0), float(COVER_BLEND), edge).mul(COVER.innerOn);
  return mix(COVER.outer.rgb, COVER.inner.rgb, w);
}
// The line map over the inner map (06e_masses' [terrain] cover_lines, tiles.json cover.inner.lines; setCover): R the
// share of a pixel under a road, G under a rail bed, B the nearest track's direction (0: none). The town layer
// draws them as asphalt and as ballast with track lines (Berlin M7 fix round: the rail and motorway corridors in the
// 20 m colour map were a mottled grey-brown smear). city.json ground.coverLines { asphalt, ballast: [dark, light],
// track, pitch, band } (linear rgb, m); off until the map is loaded
const LINES = { on: uniform(0), size: uniform(new THREE.Vector2(1, 1)), asphalt: uniform(new THREE.Color(0.075, 0.075, 0.078)),
  ballast0: uniform(new THREE.Color(0.13, 0.115, 0.1)), ballast1: uniform(new THREE.Color(0.22, 0.2, 0.18)),
  track: uniform(new THREE.Color(0.055, 0.045, 0.038)), pitch: 4.5, band: 1.7 };
LINES.map = texture(new THREE.Texture(), coverUV(COVER.innerRect));
LINES.near = textureLoad(new THREE.Texture(), ivec2(clamp(coverUV(COVER.innerRect).mul(LINES.size), vec2(0), LINES.size.sub(1))));
function coverLines(col) {
  return Fn(() => {
    const c = col.toVar();
    If(LINES.on.greaterThan(0.5), () => {
      const uvL = coverUV(COVER.innerRect).toVar();
      const inside = f01(uvL.x.greaterThan(0).and(uvL.x.lessThan(1)).and(uvL.y.greaterThan(0)).and(uvL.y.lessThan(1)));
      const L = LINES.map.toVar();
      const rail = smoothstep(0.04, 0.5, L.g).mul(inside).toVar();
      If(rail.greaterThan(0), () => {
        const code = LINES.near.b.mul(255).toVar();
        // (in 2 degree steps: a straight corridor's texels share one angle, so the lines' phase holds along it)
        const ang = code.sub(1).div(253).mul(90).round().mul(Math.PI / 90);
        const across = dot(P, vec2(sin(ang).negate(), cos(ang)));
        const tracks = pulses(across, LINES.pitch, LINES.band, fwP).mul(f01(code.greaterThan(0.5)));
        const ballast = mix(LINES.ballast0, LINES.ballast1, fbm(P.div(6), fwP.div(6), 2, 391));
        c.assign(mix(c, mix(ballast, LINES.track, tracks), rail));
      });
      c.assign(mix(c, LINES.asphalt.mul(fbm(P.div(25), fwP.div(25), 1, 393).mul(0.2).add(0.9)), smoothstep(0.2, 0.6, L.r).mul(inside)));
    });
    return c;
  })();
}
// how close the cover's colour is to a class's (1 on it, 0 a class away)
const nearClass = (c, k, r = 0.05) => float(1).sub(smoothstep(r * 0.4, r, c.sub(k).length()));

// the ground between block masses: asphalt and paving, gardens and yards under trees in patches (a petite
// couronne of blocks and pavillons with their gardens), all in world space and faded to its mean when sub-pixel
function calmTown(c = null, P = P0, fwP = fwP0) {
  // (city.json ground.townPaving [dark, light] linear, default the darker grey: the yards and pavements' range)
  const pavN = fbm(P.div(40), fwP.div(40), 3, 331);
  const paving = mix(TOWN_PAVING[0], TOWN_PAVING[1], pavN);
  const green = mix(vec3(0.045, 0.062, 0.032), vec3(0.085, 0.1, 0.05), fbm(P.div(12), fwP.div(12), 2, 333));
  const share = smoothstep(0.42, 0.62, fbm(P.div(90), fwP.div(90), 3, 335));
  // with the land cover map: its trees and grass (10 m WorldCover at 20 m a pixel), the parks, gardens and
  // tree-lined avenues between the masses, crowns in clumps; the noise's share elsewhere (built-up), lower
  c ??= coverColour();
  const wood = nearClass(c, CLASS.wood, 0.06), grass = nearClass(c, CLASS.grass, 0.06).mul(float(1).sub(wood));
  // (one noise for the crowns' clumps and shading, the lawn from the plain green's: each fbm here is paid on
  // every pixel of the town layer and the backdrop)
  const cn = fbm(P.div(7), fwP.div(7), 2, 339);
  const clumps = smoothstep(0.35, 0.6, cn);
  const crownsCol = mix(vec3(0.03, 0.045, 0.022), vec3(0.075, 0.095, 0.045), cn);
  // (city.json ground.townLawn [dark, light] linear: the cover's grass as a mown lawn of that albedo with a fine
  // mottle, as the parks' (Berlin M7 fix round: the Drachenberg's summit a near-black olive dome); default the green)
  const lawn = TOWN_LAWN ? mix(TOWN_LAWN[0], TOWN_LAWN[1], fbm(P.div(14), fwP.div(14), 2, 395))
    .mul(fbm(P.div(1.6), fwP.div(1.6), 2, 397).mul(0.3).add(0.85)) : green.mul(vec3(1.3, 1.25, 1.15));
  const coverGreen = mix(mix(paving, lawn, grass.mul(0.9)), crownsCol, wood.mul(mix(float(0.75), float(1), clumps)));
  const plain = mix(paving, green, share.mul(0.8));
  // (city.json ground.townNoiseGreen, default 0.35: the noise's green patches where the cover map is built-up; Berlin
  // 0: block interiors green only where WorldCover has trees or grass, not in blotches)
  let builtUp = mix(paving, green, share.mul(TOWN_NOISE_GREEN));
  // (city.json ground.townMapNear, 0..1, default off: the built-up land drawn in the land cover map's own colour, by
  // this share, its paving noise as a +-15 % mottle over it, instead of the paving: with 06e_masses' cover_roofs the
  // map carries the footprints as pale roofs over dark streets, which then show from the town layer's near edge on,
  // not only past its far fade at 5-9 km (Tokyo far-field fix: a pale bare plain with streets there))
  if (TOWN_MAP_NEAR) builtUp = mix(builtUp, c.mul(pavN.sub(0.5).mul(0.3).add(1)), TOWN_MAP_NEAR);
  const withCover = mix(builtUp, coverGreen, max(wood, grass));
  return coverLines(mix(plain, withCover, COVER.on).mul(fbm(P.div(700), fwP.div(700), 2, 319).sub(0.5).mul(0.25).add(1)));
}
let TOWN_LAWN = null, TOWN_NOISE_GREEN = 0.35, TOWN_MAP_NEAR = 0, TOWN_PAVING = [vec3(0.11, 0.11, 0.112), vec3(0.2, 0.195, 0.185)];
const TOWN_FAR_COVER = uniform(0);
// city.json ground.coverWater (linear RGB; default off): the land cover map's rivers and lakes beyond the ground
// area in this colour (the near river's as seen from above) instead of the map's dark olive, so the Thames past the
// ground area's edge carries on in the same tone instead of a dark painted wedge (London M7)
const COVER_WATER = uniform(new THREE.Color(0, 0, 0)), COVER_WATER_ON = uniform(0);
// city.json ground.coverWaterSky (default 0: none): with coverWater, those rivers, reservoirs and the estuary also
// mirror the sky (createGroundMaterials' waterSky: main.js's haze colour) by Schlick's Fresnel on a flat surface,
// times this share, so seen along them from the city they are bright strips as water is, not mud-coloured roads
let WATER_SKY = null, WATER_SKY_K = 0;
const WATER_SKY_U = uniform(0);
// (the cover water's colour and sky share as uniforms, for tuning from the console: __viewer.coverWater)
export const coverWater = { colour: COVER_WATER, sky: WATER_SKY_U };
// city.json ground.coverTownTint (linear rgb multiplier, default none): the land cover map's built-up colour (06e_masses'
// backdrop_town_rgb, a pale grey) tinted towards what the block masses look like from a few kilometres (their brick
// walls and slate and tile roofs), fading in over [5, 9] km where the masses fade out, so the town past the masses
// carries on in their tone rather than as pale bare patches (London M7 fix round: south from the Shard, looking east)
const TOWN_TINT = uniform(new THREE.Color(1, 1, 1)), TOWN_TINT_ON = uniform(0), TOWN_RGB_REF = uniform(new THREE.Color(0, 0, 0));
// city.json ground.townNearTint (linear rgb multiplier, default none): the ground between the town masses near the
// camera (calmTown), towards the districts' own streets and yards beside it (Berlin M3 fix round: a dark brown ring
// round pale districts)
const TOWN_NEAR_TINT = uniform(new THREE.Color(1, 1, 1));
// masses (createGroundMaterials' area.masses): whether block masses stand on it (true), none do (false), or not known
// (null: both kinds built, the uniform picks). A city's shader then holds only its own kind: New York's town layer,
// both built, was 47,000 nodes and ~140 ms of node building per pass and light (9,000 nodes, 17 ms with its own)
function townMaterial(night, masses = null) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.9, metalness: 0 });
  const townMean = uniform(new THREE.Color(0.2, 0.19, 0.17));
  const { col, street, rough } = townPattern();
  // with block masses standing on it (06e_masses: the real buildings beyond the districts), the ground between
  // them: streets, yards and gardens, no painted blocks of its own
  const calm = uniform(0);
  // far out, its mean colour (with masses: the backdrop's town colour, which its land cover map carries on)
  const far = smoothstep(float(5000), float(9000), positionWorld.distance(cameraPosition));
  // (Paris M9: in branches built from copies of their inputs: the painted blocks or the ground between the masses
  // (a uniform) and only short of the far fade; both were evaluated on every pixel, one of them weighted by 0)
  m.colorNode = Fn(() => {
    const p = P.toVar(), fw = fwP.toVar(), farK = far.toVar(), cc = masses === false ? null : coverColour().toVar();
    const out = vec3(0).toVar();
    const withMasses = () => {
      // (city.json ground.townFarCover: far out the land cover map's colour instead of the flat mean, its
      // parks and woods and, with 06e_masses' cover_roads, its street grid; default 0)
      out.assign(mix(townMean, cc, TOWN_FAR_COVER.mul(COVER.on)));
      If(TOWN_TINT_ON.greaterThan(0), () => {
        const t = float(1).sub(smoothstep(0.02, 0.06, cc.sub(TOWN_RGB_REF).length())).mul(TOWN_FAR_COVER.mul(COVER.on));
        out.assign(mix(out, out.mul(TOWN_TINT), t));
      });
      If(farK.lessThan(1), () => { out.assign(mix(calmTown(cc, p, fw).mul(TOWN_NEAR_TINT), out, farK)); });
    };
    const painted = () => {
      // far out, its mean colour, as the backdrop's towns fade (backdropMaterial: the same distances and mean)
      out.assign(mix(townMean, vec3(0.05, 0.068, 0.035), 0.2).mul(fbm(p.div(900), fw.div(900), 3, 171).sub(0.5).mul(0.35).add(1)));
      If(farK.lessThan(1), () => {
        // the same share of canopy as the backdrop's towns (backdropMaterial), so the edge draws no line
        const canopy = vec3(0.05, 0.068, 0.035).mul(fbm(p.div(30), fw.div(30), 2, 177).mul(0.5).add(0.75));
        out.assign(mix(mix(townPattern(p, fw).col, canopy, 0.12), out, farK));
      });
    };
    if (masses === true) withMasses();
    else if (masses === false) painted();
    else If(calm.greaterThan(0.5), withMasses).Else(painted);
    return out;
  })();
  m.userData.setArea = (extent, rgb, masses = false) => {
    if (rgb) townMean.value.setRGB(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, THREE.SRGBColorSpace);
    calm.value = masses ? 1 : 0;
  };
  m.roughnessNode = rough;
  // (with masses the ground between them only a little lit, dimmer than Paris: the M7 night overview read the
  // petite couronne as an even amber carpet ending in a line at the ground area's edge)
  // (Paris M9, the M7 round-2 critic: the banlieue inside ~7 km read as unlit, only an ochre wash; seen from above the
  // petite couronne is a warm sodium carpet tracing its street grid. With masses, the ground between them is the
  // street grid: lit as streets are, a glow of sodium light on the paving with the lamps as fine points on a jittered
  // ~32 m grid (kept at least about a pixel wide and dimmer as they grow, so their summed light stays the same),
  // none on the land cover's woods, grass and water: the parks and rivers stay the dark gaps)
  if (night) {
    // (ground.townLights.painted [k, r, g, b] (default none; Hong Kong M8 critic 2: the hill towns' painted roofscape
    // read as orange stripes from the overview): the painted town's night light times k, tinted by the linear rgb)
    const PT = TOWN_PAINTED_LIT;
    const plain = PT ? col.mul(yardLamps(30, 0.3, 0.05, float(1).sub(street))).mul(vec3(...PT.slice(1, 4)).mul(PT[0]))
      : col.mul(yardLamps(30, 0.3, 0.05, float(1).sub(street)));
    const lights = masses === false ? plain : Fn(() => {
      const e = vec3(0).toVar();
      const p = P.toVar(), fw = fwP.toVar(), cc = coverColour().toVar();
      const lit = () => {
        const green = max(nearClass(cc, CLASS.wood, 0.06), max(nearClass(cc, CLASS.grass, 0.06), nearClass(cc, CLASS.water, 0.03)));
        const g = p.div(32), gi = floor(g);
        const jit = vec2(hashI(gi.x, gi.y, 371), hashI(gi.x, gi.y, 373)).mul(0.8).add(0.1);
        const d = fract(g).sub(jit).mul(32);
        const r = max(float(2.5), fw.mul(0.8));
        const post = exp(dot(d, d).div(r.mul(r).negate())).mul(float(10).div(r.mul(r))).mul(f01(hashI(gi.x, gi.y, 375).lessThan(0.6)));
        // (ground.townLights.led, default none: sodium to warm LED; Singapore M8: a share of white LED among warm LED)
        const tint = TOWN_LED == null ? mix(SODIUM, WARM_LED, hashI(gi.x, gi.y, 377).mul(0.5))
          : mix(WARM_LED, TOWN_WHITE ? vec3(...TOWN_WHITE) : LED, f01(hashI(gi.x, gi.y, 377).lessThan(TOWN_LED)));
        e.assign(tint.mul(post.add(STREET_GLOW.base)).mul(STREET_GLOW.gain).mul(float(1).sub(green.mul(COVER.on))));
      };
      if (masses === true) lit();
      else If(calm.greaterThan(0.5), lit).Else(() => { e.assign(plain); });
      return e;
    })();
    night.withLights(m, lights);
  }
  m.userData.streetGlow = STREET_GLOW;
  return m;
}

// courtyard, plaza and path lamps: a jittered grid of posts `cell` m apart, a share of them there (and only
// where `where` is 1: some lots have them, others are dark), low, of different makes and heights, so their
// pools differ in size and brightness; plus a faint spill from the streets and windows around (`base`).
// Their mean once the pools get smaller than a few pixels (a grid of bright dots reads as a pattern, not
// as lamps)
// (city.json ground.yardBase: the even spill term's factor, 1 by default; Berlin M8 fix round 0.4: pavements and plazas an
// even ochre wash with no pools)
let YARD_BASE = 1;
let APRON = null, PLAZA_LAMPS = null;
// (city.json ground.litAreas [{ at: [x, z], r, k, colour }], default none (Tokyo M8 fix round 1): circles (scene m) where the
// ground's paving, plazas and pavements are lit evenly after dark, k times colour on the surface's own colour, fading over
// the circle's outer 30 %: the spill of a commercial district's blazing shopfronts and plaza lamps (Shibuya's Hachiko
// square, Akihabara's and Kabukicho's pavements read dark brown between lit roads); roads take `roads` of it (default 0.3))
let LIT_AREAS = null, LIT_ROADS = 0.3;
const litAreas = (share = 1) => {
  let e = vec3(0, 0, 0);
  for (const a of LIT_AREAS) {
    const w = float(1).sub(smoothstep(float(a.r * 0.7), float(a.r), P.sub(vec2(a.at[0], a.at[1])).length()));
    e = e.add(vec3(...(a.colour ?? [1, 0.95, 0.88])).mul(w.mul((a.k ?? 1) * share)));
  }
  return e;
};
function yardLamps(cell, share, base, where = float(1)) {
  const q = P.div(cell);
  const i = floor(q);
  const h = hashI(i.x, i.y, 181);
  const j = vec2(hashI(i.x, i.y, 183), hashI(i.x, i.y, 187)).mul(0.7).add(0.15);
  const d = fract(q).sub(j).mul(cell);
  // (pool size: exp(-r2 / s), s from 8 to 30 m2; brighter where wider)
  const size = mix(float(8), float(30), hashI(i.x, i.y, 191));
  const pool = exp(dot(d, d).div(size.negate())).mul(size.div(30)).mul(f01(h.lessThan(share)));
  const mean = float(share * Math.PI * 13.4 / (cell * cell));          // (the pools' integral, E[s^2] / 30)
  const colour = mix(WARM_LED, LED, hashI(i.x, i.y, 189).mul(0.7));
  return mix(mix(WARM_LED, LED, 0.35).mul(mean), colour.mul(pool), resolved(fwP.div(4))).mul(where).mul(0.35).add(WARM_LED.mul(base * YARD_BASE));
}

// the tree crown seen from above at p: of the jittered points of a unit grid around it, the one whose dome
// (radius from its id, present with probability `coverage`) stands highest here, so crowns overlap as round
// discs, the bigger over the smaller, with lawn between them; the nearest point (Worley F1) instead cut
// packed crowns along its cells' edges into a hexagonal mosaic ("grass is a blotchy hex pattern", Paris M4)
function crowns(p, salt, coverage) {
  const i = floor(p), f = fract(p);
  let best = float(-1), id = float(0), off = vec2(0, 0), rad = float(0.5);
  for (let dx = -1; dx <= 1; dx++) {
    for (let dy = -1; dy <= 1; dy++) {
      const cx = i.x.add(dx), cy = i.y.add(dy);
      const j = vec2(hashI(cx, cy, salt), hashI(cx, cy, salt + 1)).mul(0.7).add(0.15);
      const o = vec2(dx, dy).add(j).sub(f);
      const hid = hashI(cx, cy, salt + 2);
      const r = hid.mul(0.3).add(0.5);
      const here = f01(hashI(cx, cy, salt + 5).lessThan(coverage));
      const h = float(1).sub(dot(o, o).div(r.mul(r))).mul(r).mul(here).sub(float(1).sub(here).mul(2));
      const higher = f01(h.greaterThan(best));
      best = mix(best, h, higher);
      id = mix(id, hid, higher);
      off = mix(off, o, higher);
      rad = mix(rad, r, higher);
    }
  }
  return { id, off, radius: rad, present: f01(best.greaterThan(-1.5)) };
}

// nearest jittered point of a unit grid (Worley F1): squared distance, the offset from p to that point
// and a random id for it. Branchless over the 3 x 3 neighbourhood.
function worley(p, salt) {
  const i = floor(p), f = fract(p);
  let best = float(9), id = float(0), off = vec2(0, 0);
  for (let dx = -1; dx <= 1; dx++) {
    for (let dy = -1; dy <= 1; dy++) {
      const cx = i.x.add(dx), cy = i.y.add(dy);
      const j = vec2(hashI(cx, cy, salt), hashI(cx, cy, salt + 1)).mul(0.7).add(0.15);
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

const CROWN = 6;              // metres between tree crowns

// lawnStyle (city.json ground.lawnStyle, optional): { patches: tone swing of the 50-200 m patches of greener and
// drier grass (0), dry: the drier patches' colour (linear), worn: how much of the trodden bare patches shows (0.6) }
function greenMaterial(sunDir, night, lawnColours, lawnStyle = {}) {
  const LS = { patches: 0, dry: [0.16, 0.15, 0.07], worn: 0.6, ...lawnStyle };
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.95, metalness: 0 });
  // tree cover: large-scale density (closed woodland vs open lawn with scattered trees)
  let density = smoothstep(0.3, 0.7, fbm(P.div(170), fwP.div(170), 3, 41));
  // (city.json ground.lawnStyle.cover, 0..1, default 0: where the land cover map has grass the canopy opens to lawn,
  // so an open hill meadow is not the noise's dark understory: the Drachenberg's summit, Berlin M7 critic)
  if (LS.cover) density = density.mul(float(1).sub(nearClass(coverColour(), CLASS.grass, 0.09).mul(COVER.on).mul(LS.cover)));
  const coverage = mix(float(0.18), float(1.05), density);
  // crowns: domes around jittered points, lit from the sun's side. The lighting already shades the flat
  // ground by the sun's elevation, so a dome point is scaled by n.l relative to flat ground's
  const q = P.div(CROWN);
  const w = crowns(q, 43, coverage);
  const radius = w.radius;                                    // crown radius in cell units
  const present = w.present;
  const rel = w.off.div(radius);                              // from here to the crown centre, / radius
  // leaf clumps (also roughen the crown outline, so crowns packed together don't show cell facets)
  const foliage = fbm(P.div(1.1), fwP.div(1.1), 2, 47);
  const r2 = dot(rel, rel).add(foliage.sub(0.5).mul(0.5));
  const fwq = fwP.div(CROWN);
  const inside = below(float(1).sub(fwq.mul(2)), float(1).add(fwq.mul(2)), r2).mul(present);
  const up = float(1).sub(r2).max(0.02).sqrt();
  const nrm = vec3(rel.x.negate(), up.mul(0.8), rel.y.negate()).normalize();
  // a live uniform on the viewer's sun direction, so the time-of-day setting relights the crowns
  const sun = uniform(sunDir);
  const lit = clamp(dot(nrm, sun).div(sun.y.max(0.05)), 0, 1.8);
  // leaf texture inside a crown (clumps of foliage) and per-tree hue: most evergreen dark, some light
  const leaf = mix(mix(vec3(0.028, 0.06, 0.02), vec3(0.06, 0.1, 0.03), w.id),
    vec3(0.09, 0.12, 0.04), f01(w.id.greaterThan(0.88)))
    .mul(foliage.mul(0.6).add(0.7));
  const crownCol = leaf.mul(lit.mul(0.6).add(0.4));
  // between crowns: lawn in parks, dark understory under closed canopy
  const lawnN = fbm(P.div(12), fwP.div(12), 3, 59).mul(0.6).add(fbm(P.div(3.1), fwP.div(3.1), 2, 63).mul(0.4));
  const blades = mix(float(0.5), vnoise(P.div(0.25), 67), resolved(fwP.div(0.25)));
  // lawns under a hazy sky are a cool, muted green (Shenzhen's, the default); the warm sun and neutral tone
  // mapping push anything with little blue towards yellow-olive, so the base keeps about half as much blue
  // as green
  const lawn = mix(vec3(...lawnColours[0]), vec3(...lawnColours[1]), lawnN)
    .mul(foliage.mul(0.3).add(0.85)).mul(blades.mul(0.3).add(0.85));
  const worn = smoothstep(0.72, 0.8, fbm(P.div(25), fwP.div(25), 3, 61));
  let lawnCol = mix(lawn, vec3(0.19, 0.16, 0.11), worn.mul(LS.worn));
  if (LS.patches) {
    // large patches: greener where it is wetter or shaded, drier and yellower on the open, trodden expanses
    const patch = fbm(P.div(120), fwP.div(120), 3, 65).mul(0.7).add(fbm(P.div(48), fwP.div(48), 2, 69).mul(0.3));
    lawnCol = mix(lawnCol, vec3(...LS.dry), smoothstep(0.5, 0.8, patch).mul(LS.patches))
      .mul(patch.sub(0.5).mul(LS.patches * 0.6).add(1));
  }
  // shadow of the crown on the sun-away side, then understory where the canopy closes
  const shadowRel = w.off.add(vec2(sun.x, sun.z).mul(0.45)).div(radius);
  // painted crowns only where the real (instanced) trees aren't drawn: beyond their range, or with trees
  // switched off; nearer, the ground under them is plain lawn or understory (trees.js casts the shadows)
  const treesOn = uniform(1);
  const paint = max(float(1).sub(treesOn), smoothstep(float(4200), float(4800), distance(positionWorld, cameraPosition)));
  const shadow = below(float(0.8), float(1.2), dot(shadowRel, shadowRel)).mul(present).mul(paint);
  const gap = mix(lawnCol.mul(float(1).sub(shadow.mul(0.55))), vec3(0.018, 0.03, 0.012), density.mul(0.85));
  const near = mix(gap, crownCol, inside.mul(paint));
  // crowns smaller than a few pixels: their average instead (coverage of about 60 % of the ground)
  const avgCover = min(coverage, 1).mul(0.6).mul(paint);
  const far = mix(mix(lawnCol, vec3(0.022, 0.035, 0.015), density.mul(0.85)), leaf.mul(0.95), avgCover);
  m.colorNode = rockFace(mix(far, near, resolved(fwq, 3)));
  m.roughnessNode = float(0.9);
  // park paths: fewer lamps, dark lawns and woods between
  if (night) night.withLights(m, m.colorNode.mul(yardLamps(30, 0.1, 0.02)));
  m.userData.nodes = { density, inside, lit };
  m.userData.treesOn = treesOn;                 // set by the viewer's trees switch
  return m;
}

// tones: the concrete's darker and lighter linear albedo (city.json's ground.aeroway)
// heading: of the airport's main runway (compass degrees, city.json's ground.airportHeading; 06b_markings.py
// prints it; 154.3 at Shenzhen Bao'an): the concrete panels of aprons and taxiways follow it
function aerowayMaterial(night, heading, tones = [[0.34, 0.34, 0.325], [0.42, 0.415, 0.395]]) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.85, metalness: 0 });
  const a = THREE.MathUtils.degToRad(heading);
  // scene x = east, z = south: along the runway is (sin a, -cos a)
  const ax = float(Math.sin(a)), az = float(-Math.cos(a));
  const q = vec2(P.x.mul(ax).add(P.y.mul(az)), P.x.mul(az.negate()).add(P.y.mul(ax)));   // (along, across)
  const panel = floor(q.div(5));
  const pv = hash2(panel, 71);
  const joints = max(pulses(q.x, float(5), float(0.1), fwP), pulses(q.y, float(5), float(0.1), fwP));
  const zone = fbm(P.div(120), fwP.div(120), 3, 73);
  const stains = fbm(P.div(4), fwP.div(4), 4, 79);
  const oil = smoothstep(0.6, 0.8, fbm(P.div(10), fwP.div(10), 3, 83));
  const base = mix(vec3(...tones[0]), vec3(...tones[1]), zone)
    .mul(mix(float(1), pv.mul(0.12).add(0.94), resolved(fwP.div(5))));
  m.colorNode = base.mul(float(1).sub(joints.mul(0.35))).mul(stains.sub(0.5).mul(0.3).add(1)).mul(float(1).sub(oil.mul(0.35)));
  // aprons under high-mast floodlights: bright and fairly even, sodium and white masts
  // (city.json ground.apronLights { colour, k }, default none (Singapore M8 fix round 1: the terminals' orange clouds):
  // the high masts' white light (colour, linear) on the concrete's mean tone, no cloudy zones: a gentle swell under each
  // mast of a 90 m grid (smooth: no cell edges), k the strength)
  if (night && APRON) {
    const q = P.mul(Math.PI * 2 / 90);
    const pool = cos(q.x).mul(cos(q.y)).mul(0.1).add(0.95);
    const mean = mix(vec3(...tones[0]), vec3(...tones[1]), 0.5).mul(float(1).sub(joints.mul(0.35)));
    night.withLights(m, mean.mul(vec3(...(APRON.colour ?? [0.92, 0.95, 1]))).mul(pool).mul(APRON.k ?? 0.3));
  } else if (night) {
    const mast = floor(P.div(90));
    const flood = mix(SODIUM, LED, hashI(mast.x, mast.y, 191)).mul(mix(float(0.5), float(1), zone));
    night.withLights(m, m.colorNode.mul(flood).mul(0.3));   // (1.1 bloomed small pads, the heliports, into glowing orbs)
  }
  return m;
}

function roadMaterial(night, sodium) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.9, metalness: 0 });
  const vc = vertexColor().rgb;
  const rail = vc.x.sub(vc.z).greaterThan(0.03);       // 06_tiles.py colours railways warm grey-brown
  const ballast = vec3(0.2, 0.18, 0.155).mul(mix(float(0.5), vnoise(P.div(0.25), 89), resolved(fwP.div(0.25))).mul(0.5).add(0.75));
  m.colorNode = sel(rail, ballast, (ASPHALT_K ? vc.mul(vec3(...ASPHALT_K)) : vc).mul(asphaltFactor()));
  m.roughnessNode = float(0.9);
  // what shows of the road mesh are mostly junctions: lit from every side, at a little over the streets'
  // mean (no lamp posts: its polygons have no along and across); and minor roads without markings (estate
  // and service roads, drives round the podiums), lit evenly they read as pale outlines drawn round the
  // blocks: pools under the odd lamp instead, darker between. Railways stay dark
  if (night) {
    const minor = f01(vc.x.greaterThan(0.115));        // (06_tiles.py's minor road grey is lighter)
    let junction = regionLamp(float(1), float(0), sodium).mul(STREET * 0.55);
    if (JUNCTION_POOLS) {
      // (the four nearest lamps of the grid, their light over its mean, the mean itself once the cells are small)
      const { cell, h } = JUNCTION_POOLS;
      const q = P.div(cell).sub(0.5), i0 = floor(q);
      let sum = float(0);
      for (const [a, b] of [[0, 0], [1, 0], [0, 1], [1, 1]]) {
        const ix = i0.x.add(a), iz = i0.y.add(b);
        const j = vec2(hashI(ix, iz, 211), hashI(ix, iz, 213)).mul(0.6).add(0.2);
        const d = vec2(ix, iz).add(j).sub(q).mul(cell);
        sum = sum.add(lampAt(dot(d, d), h));
      }
      const mean = (2 * Math.PI * h * h) / (cell * cell);
      junction = junction.mul(mix(float(1), sum.div(mean), resolved(fwP.div(cell), 3))).mul(JUNCTION_POOLS.k);
    }
    night.withLights(m, m.colorNode.mul(mix(junction, yardLamps(16, 0.6, 0).mul(10), minor)).mul(f01(rail.not())).mul(PROC()));
  }
  return m;
}

// bridge decks and their pillars (vertex colours): the deck's top lit like a street
function bridgeMaterial(night, sodium) {
  const m = new THREE.MeshStandardNodeMaterial({ vertexColors: true, roughness: 0.85, metalness: 0 });
  if (night) {
    const top = smoothstep(0.8, 0.95, normalWorldGeometry.y);
    // the suspension bridges' "necklaces": a lamp every 14 m along each main cable (uv.y 50000 marks one,
    // uv.x runs along it, 06_tiles / structures.py), a string of white dots; their mean once under a pixel
    const cable = f01(abs(uv().y.sub(50000)).lessThan(0.5));
    const fw = max(fwidth(uv().x), 1e-4);
    const beads = pulses(uv().x, float(14), float(1.6), fw);
    // floodlit bridges (night.floodBridges; 0: none): their walls, piers and pylons washed in the flood light's
    // colour, and gilt (strongly gold-coloured parts: the Pont Alexandre III's Pegasus groups) glowing gold
    const vc = vertexColor().rgb;
    const gilt = smoothstep(2.5, 5, vc.x.div(max(vc.z, 0.01))).mul(smoothstep(0.15, 0.3, vc.x));
    const wash = vc.mul(night.floodTint).mul(float(1).sub(top).mul(0.12).add(gilt.mul(1.1))).mul(night.floodBridges);
    night.withLights(m, vc.mul(regionLamp(float(1), float(1), sodium)).mul(top).mul(STREET * 0.5).mul(PROC())
      .add(vec3(1, 0.95, 0.85).mul(beads).mul(cable).mul(14)).add(wash));
  }
  return m;
}

// ---------------------------------------------------------------- markings
const WHITE = vec3(0.72, 0.72, 0.69), YELLOW = vec3(0.68, 0.45, 0.06);

// conventions: city.json's markings (centreColour 'yellow' or 'white', or { big, small } by road size; dashes [period, painted] in metres);
// sodium: the street lamps' shares (regionLamp)
// zebra: the crossing's bars ({ bar, gap, from, to }: bar width and gap across the road, from/to metres from
// the junction; default 0.45 m bars every 1 m from 0.5 to 4.5 m), stopLine: [from, to] m (default 5.3-5.7),
// lineWidth: lane and edge lines on [small, big] roads (default 0.15, 0.2)
// edgeLines: the solid edge lines 0.3 m in from the kerbs (false: none, as on most French city streets);
// stopInset: how far the stop line stops short of the kerb (m; 2.3 leaves a parking lane out)
// UK-style options (06b_markings' flags; London M5): bigCentre 'double' (two solid lines on big two-way roads)
// or 'dashed' (the single dashed centre line, as on UK roads); kerbLines { yellow, red: linear rgb, w, at: [the
// two lines' centres from the kerb] } for the double yellow and red lines; busLane { w, line, red }: lane width,
// boundary line width, red surfacing (linear); cycleLane { w, line, dashes, colour (linear or null) }; nearside
// 'left' or 'right' (the kerb a one-way road's cycle lane runs along: the driving side's)
// German options (Berlin M5; all off or unchanged by default): bigCentre 'solid' (one solid line on big two-way roads);
// giveWay 'teeth' (Haifischzähne instead of the two rows of dashes); zebra.mid { half, period, bar, give } (the OSM
// zebras between junctions: half their length, the bars' period and width, the give-way line), zebra.zigzags false,
// zebra.signal { studs, w, period, on, stop, stopW } (signal crossings between junctions: the Furt lines' distance from
// the middle, width, dash period and length; the stop line's), zebra.studs { at, w, period, on } (the junction arms'
// crossing lines, m from the junction); setts { tone: [linear rgb x2], row, stone } (06b's sett carriageways, b bit
// 128: granite setts in rows across, no lane paint); sidewalk.style2 (06b's sidewalk style 1, Berlin's Gehweg:
// { mosaic: rgb, slab: rgb, plate: rgb, granite: share of blocks in granite slabs, slabSize: [w, l], under: [share of
// the width, min, max], over: [share, min, max] }); tram { rail, groove, ballast, sleeper, grass: rgb } (06b's tram
// strips, type 8)
function markingsMaterial({ uvRange }, night, { centreColour, dashes, sidewalk = {}, zebra: zebraOpt = {}, stopLine = [5.3, 5.7],
  lineWidth = [0.15, 0.2], edgeLines = true, stopInset = 0.3, bigCentre = 'double', kerbLines = {}, busLane = {}, cycleLane = {},
  nearside = 'right', repaving = {}, giveWay: giveWayStyle = 'dashes', setts: settsOpt = {}, tram: tramOpt = null }, sodium) {
  const KL = { yellow: [0.62, 0.46, 0.05], red: [0.42, 0.04, 0.04], w: 0.075, at: [0.16, 0.31], ...kerbLines };
  const BL = { w: 3.2, line: 0.25, red: [0.2, 0.045, 0.035], ...busLane };
  const CL = { w: 1.5, line: 0.15, dashes: [6, 4], colour: null, ...cycleLane };
  const ZB = { bar: 0.45, gap: 0.55, from: 0.5, to: 4.5, ...zebraOpt };
  // sidewalks (city.json markings.sidewalk): paving colour and flag size, the share of blocks paved in red brick,
  // the bike lane's colour on wide sidewalks (null: none), a tactile strip along them, flowering medians, tree
  // pits every 8 m (false where the street trees are real and stand where they stand)
  // (flag null: poured asphalt, no joints, as most of Paris's sidewalks; kerb: the kerbstone's colour and width,
  // granite speckled when `granite`; gutter: the stone gutter's width along the kerb on the carriageway side, with a
  // dark line in the kerb's corner that reads in shadow too (m, 0: none))
  const SW = { paving: [0.33, 0.31, 0.28], flag: [0.3, 0.6], red: 0.28, bike: [0.19, 0.075, 0.065], tactile: true,
    flowers: true, pits: true, kerb: [0.46, 0.45, 0.43], kerbW: 0.22, granite: false, gutter: 0, ...sidewalk };
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.88, metalness: 0 });
  // centre lines and the median side's edge line
  // (centreColour { big, small }, opt-in, Tokyo M5: the centre line's colour by road size, Japan's yellow no-overtaking
  // line on the big two-way roads and white on the small ones; a string: one colour for all, as before)
  const colourOf = (cc) => (cc === 'white' ? WHITE : YELLOW);
  const centreBySize = centreColour !== null && typeof centreColour === 'object';
  let CENTRE = centreBySize ? null : colourOf(centreColour);
  const c = vertexColor().mul(255).add(0.5).floor();                   // integer channels
  const type = c.x, halfW = c.y.div(4), code = c.z, flag = c.w;
  const is = (t) => f01(abs(type.sub(t)).lessThan(0.5));
  const tLanes = is(0), tCross = is(1), tSide = is(2), tMedian = is(3), tRunway = is(4), tPlaza = is(5), tZebra = is(6), tBeacon = is(7);
  const tTram = is(8);
  const across = uv().x.mul(2 * uvRange.across).sub(uvRange.across);
  const along = uv().y.mul(uvRange.along);
  const fwA = max(fwidth(across), 1e-4), fwL = max(fwidth(along), 1e-4);
  const nLanes = mod(code, 16);
  const bit = (v, b) => mod(floor(v.div(b)), 2);
  const oneway = bit(code, 16), big = bit(code, 32), motorway = bit(code, 64);
  if (centreBySize) CENTRE = mix(colourOf(centreColour.small), colourOf(centreColour.big), big);

  // ---- asphalt (lanes, crossings): the road mesh's colour and grain, plus wear aligned with the lanes
  const kindCol = mix(ROAD_MINOR, ROAD_MAJOR, big);
  const x = mix(abs(across), across.add(halfW), oneway);              // distance from centre (one-way: right edge)
  const lw = halfW.mul(mix(float(1), float(2), oneway)).div(max(nLanes, 1));
  const inLane = fract(x.div(lw));
  // oil drips down the middle of each lane, polished wheel paths either side
  const laneRes = resolved(fwA.div(lw).mul(4));
  const oilLine = below(0.0, 0.28, abs(inLane.sub(0.5))).mul(laneRes);
  const wheel = below(0.0, 0.1, abs(abs(inLane.sub(0.5)).sub(0.26))).mul(laneRes);
  const oilVar = fbm(vec2(across.mul(0.5), along.div(6)), fwL.div(6), 2, 97);
  // repaving patches: rectangles whole lanes wide and 15-60 m long, darker (new) or lighter (old); city.json
  // markings.repaving { share, dark, light } (the defaults: 16 % of the cells, x 0.72 or x 1.22). London M9 round 2: at
  // that contrast the dark ones read as translucent shadows behind the cars at the Strand (and as wedges where a
  // strip's lanes widen, the lane cells running across them): London takes { share: 0.08, dark: 0.9, light: 1.08 }
  const RP = { share: 0.16, dark: 0.72, light: 1.22, ...repaving };
  const patchLen = float(37);
  const pCell = floor(along.div(patchLen));
  const pLane = floor(x.div(lw));
  const pH = hashI(pCell, pLane.add(oneway.mul(50)), 101);
  const pStart = hashI(pCell, pLane, 103).mul(0.5), pEnd = pStart.add(hashI(pCell, pLane, 107).mul(0.5));
  const inPatch = f01(pH.lessThan(RP.share)).mul(span(fract(along.div(patchLen)), pStart, pEnd, fwL.div(patchLen)));
  const patchTone = sel(hashI(pCell, pLane, 109).lessThan(0.6), float(RP.dark), float(RP.light));
  const grainK = asphaltFactor();          // built once and shared by the asphalt, bike lane and runway
  let asphalt = kindCol.mul(grainK)
    .mul(float(1).sub(oilLine.mul(oilVar.mul(0.35).add(0.05))).add(wheel.mul(0.05)))
    .mul(mix(float(1), patchTone, inPatch));
  if (SW.gutter) {
    // the caniveau: granite setts or a stone strip along the kerb, paler than the asphalt; a dark line where it
    // meets the kerb's face
    const toKerb = halfW.sub(abs(across));
    const gutterCol = vec3(...SW.kerb).mul(0.72).mul(mix(float(0.5), hashI(floor(along.div(0.22)), floor(toKerb.div(0.16)), 145), resolved(fwL.div(0.22))).mul(0.16).add(0.92));
    asphalt = mix(asphalt, gutterCol, span(toKerb, float(0.07), float(SW.gutter), fwA));
    asphalt = mix(asphalt, kindCol.mul(SW.gutterShade ?? 0.35), span(toKerb, float(-0.02), float(0.07), fwA));
  }

  // ---- setts (Kopfsteinpflaster; b bit 128 on lanes and crossings): granite setts in rows across the road, each row
  // offset, stones of varying tone with dark sandy joints; their mean once the rows are sub-pixel
  const SE = { tone: [[0.15, 0.148, 0.142], [0.25, 0.245, 0.235]], row: 0.16, stone: 0.13, ...settsOpt };
  const settsAt = (acr, alg, fa, fl) => {
    const row = floor(alg.div(SE.row));
    const off = hashI(row, float(7), 171);
    const st = floor(acr.div(SE.stone).add(off));
    const tone = hashI(st, row, 173);
    const res = resolved(max(fa.div(SE.stone), fl.div(SE.row)));
    const stone = mix(vec3(...SE.tone[0]), vec3(...SE.tone[1]), mix(float(0.45), tone, res));
    const joints = max(pulses(alg, float(SE.row), float(0.025), fl), pulses(acr.div(SE.stone).add(off), float(1), float(0.18), fa.div(SE.stone)));
    return stone.mul(float(1).sub(joints.mul(0.45)));
  };
  // (one sett pattern serves the carriageway and the tram beds: in the same (across, along) frame; every branch of the
  // material is evaluated per fragment, so nothing here is built twice)
  // (the new surfaces below are drawn in branches of the colour Fn at the end: every term of the material is
  // otherwise evaluated by every markings fragment, and they cost the overview 24 ms, 13 %, as plain terms)
  const useSetts = !!(settsOpt && Object.keys(settsOpt).length);
  const settsHere = () => settsAt(across, along, fwA, fwL).mul(grainK);
  const isSetts = useSetts ? bit(code, 128).mul(tLanes.add(tCross)) : float(0);

  // ---- paint: worn in places, box-filtered lines
  const wear = fbm(vec2(across.mul(1.5), along.div(1.2)), max(fwA.mul(1.5), fwL.div(1.2)), 3, 113);
  const paintK = smoothstep(0.15, 0.55, wear).mul(0.35).add(0.65);
  // dashes (by default Chinese GB 5768's: 2 m every 6 m on small streets, 4 m every 10 m on arterials, 6 m
  // every 15 m on expressways); all periods must divide 06b_markings.py's along wrap
  const dashP = mix(mix(float(dashes.street[0]), float(dashes.arterial[0]), big), float(dashes.motorway[0]), motorway);
  const dashOn = mix(mix(float(dashes.street[1]), float(dashes.arterial[1]), big), float(dashes.motorway[1]), motorway);
  const dash = pulses(along, dashP, dashOn, fwL);
  const lineW = mix(float(lineWidth[0]), float(lineWidth[1]), big);
  // lane dividers: at whole lanes (x = k lw, k = 1..n-1) between the edges, dashed white. pulses() centres
  // its lines on multiples of the period, so x goes in as it is; lane centres, where 06d_cars.py drives,
  // are at (k + 0.5) lw
  const inner = f01(x.greaterThan(lw.mul(0.5)).and(x.lessThan(lw.mul(nLanes.sub(0.5)))));
  const divider = pulses(x, lw, lineW, fwA).mul(inner).mul(dash);
  // edges: solid, 0.3 m in from the edge of the carriageway (left edge of a one-way carriageway of a dual
  // road is the centre line's colour, it faces oncoming traffic across the median)
  const hasLines = f01(nLanes.greaterThan(0.5));
  const edgeR = line(across, halfW.negate().add(0.3), lineW, fwA);
  const edgeL = line(across, halfW.sub(0.3), lineW, fwA);
  const edgeOn = hasLines.mul(f01(halfW.greaterThan(3.2))).mul(edgeLines ? 1 : 0);
  const yellowLeft = bit(flag, 1).mul(oneway);
  // centre of two-way roads: double solid on big roads, single dashed on small ones (yellow or white)
  const twoWay = float(1).sub(oneway).mul(hasLines);
  const dbl = max(line(across, float(0.2), float(0.15), fwA), line(across, float(-0.2), float(0.15), fwA));
  // (the warning line, flag 64, within a few dozen metres of a junction: longer marks, same period)
  const warnBit = bit(flag, 64).mul(tLanes);
  const wd = dashes.warning ?? dashes.centre;
  const cP = mix(float(dashes.centre[0]), float(wd[0]), warnBit), cOn = mix(float(dashes.centre[1]), float(wd[1]), warnBit);
  const single = line(across, float(0), float(bigCentre === 'dashed' ? lineWidth[1] : 0.15), fwA).mul(pulses(along, cP, cOn, fwL));
  const centre = twoWay.mul(bigCentre === 'dashed' ? single
    : bigCentre === 'solid' ? mix(single, line(across, float(0), float(lineWidth[1]), fwA), big) : mix(single, dbl, big));
  // bus lanes (flags 2, 4: along the left / right kerb; 8 red-surfaced) with their solid boundary line; cycle
  // lanes (128) along the kerbs without one, a dashed line; kerb lines (16 x k: double yellow, double red)
  const toL = halfW.sub(across), toR = halfW.add(across);            // metres from the left / right kerb
  const busL = bit(flag, 2).mul(tLanes), busR = bit(flag, 4).mul(tLanes);
  const busW = min(float(BL.w), halfW.mul(0.48));
  const inBus = max(busL.mul(span(toL, float(0), busW, fwA)), busR.mul(span(toR, float(0), busW, fwA)));
  const busLine = max(busL.mul(line(toL, busW, float(BL.line), fwA)), busR.mul(line(toR, busW, float(BL.line), fwA)));
  asphalt = mix(asphalt, vec3(...BL.red).mul(grainK), inBus.mul(bit(flag, 8)));
  // (busLane.legend: "BUS" across the lane every `legend` m, letters 0.9 m wide and 2.5 m long on a 3 x 5 grid, read by
  // the lane's own traffic; their mean once the grid is sub-pixel)
  let busLegend = null;
  if (BL.legend) {
    const glyph = (toK, flip) => {
      const u = busW.sub(toK).sub(busW.sub(3.1).mul(0.5));
      const li = floor(u.div(1.05)), cu = u.sub(li.mul(1.05));
      const v = mod(along, float(BL.legend)).sub(4);
      const rv = floor(v.div(0.5));
      const ri = flip ? rv : float(4).sub(rv);
      const ci = floor(cu.div(0.3));
      const N = sel(li.lessThan(0.5), float(0b110101110101110), sel(li.lessThan(1.5), float(0b111101101101101), float(0b111001111100111)));
      const on = mod(floor(N.add(0.5).div(pow(float(2), ri.mul(3).add(float(2).sub(ci))))), 2);
      const inside = f01(u.greaterThan(0).and(li.lessThan(2.5)).and(cu.lessThan(0.9)).and(v.greaterThan(0)).and(v.lessThan(2.5)));
      return on.mul(inside);
    };
    busLegend = () => max(busR.mul(glyph(toR, false)), busL.mul(glyph(toL, true))).mul(resolved(fwL.div(0.5)));
  }
  const cyc = bit(flag, 128).mul(tLanes);
  const cycL = cyc.mul(float(1).sub(busL)).mul(nearside === 'left' ? float(1) : float(1).sub(oneway));
  const cycR = cyc.mul(float(1).sub(busR)).mul(nearside === 'right' ? float(1) : float(1).sub(oneway));
  const cycDash = pulses(along, float(CL.dashes[0]), float(CL.dashes[1]), fwL);
  const cycLine = max(cycL.mul(line(toL, float(CL.w), float(CL.line), fwA)), cycR.mul(line(toR, float(CL.w), float(CL.line), fwA))).mul(cycDash);
  if (CL.colour) asphalt = mix(asphalt, vec3(...CL.colour).mul(grainK), max(cycL.mul(span(toL, float(0.3), float(CL.w), fwA)), cycR.mul(span(toR, float(0.3), float(CL.w), fwA))));
  const kerbK = mod(floor(flag.div(16)), 4).mul(tLanes.add(tCross));
  const kerbOn = f01(kerbK.greaterThan(0.5));
  const dblLine = (o) => max(line(o, float(KL.at[0]), float(KL.w), fwA), line(o, float(KL.at[1]), float(KL.w), fwA));
  const kerbPaint = kerbOn.mul(max(dblLine(toL), dblLine(toR)));
  const kerbLineCol = mix(vec3(...KL.yellow), vec3(...KL.red), f01(kerbK.greaterThan(1.5)));
  // (the divider next to a bus lane is its boundary line)
  const whiteLanes = clamp(divider.mul(float(1).sub(inBus)).add(edgeR.mul(edgeOn)).add(edgeL.mul(edgeOn).mul(float(1).sub(yellowLeft)))
    .add(busLine).add(cycLine), 0, 1);
  const yellowLanes = clamp(centre.add(edgeL.mul(edgeOn).mul(yellowLeft)), 0, 1);

  // ---- crossings: along runs from the junction (0) outwards. Zebra 0.5-4.5 m, stop line at 5.3-5.7 m
  // on the side(s) whose traffic approaches the junction
  // the junction's marking (flags 4 x k): 0 a zebra and stop line, 1 a give-way line (two rows of 0.6 m dashes)
  // across the approach half, 2 signals: the crossing's two broken stud lines and the stop line, 3 none
  const jStyle = mod(floor(flag.div(4)), 4);
  const jZebra = f01(jStyle.lessThan(0.5)), jGive = f01(abs(jStyle.sub(1)).lessThan(0.5));
  const jSignal = f01(abs(jStyle.sub(2)).lessThan(0.5));
  // (zebra.atSignals, opt-in, Tokyo M5: a signalled arm takes the zebra and stop line, not the stud lines: Japan's
  // signalled junctions; giveWay 'stop': an arm with a give-way gets a stop line instead, Japan's 止まれ arms)
  const zebraArms = ZB.atSignals ? jZebra.add(jSignal) : jZebra;
  const zebra = span(along, float(ZB.from), float(ZB.to), fwL).mul(pulses(across.add(halfW), float(ZB.bar + ZB.gap), float(ZB.bar), fwA))
    .mul(span(across, halfW.negate().add(0.4), halfW.sub(0.4), fwA)).mul(zebraArms);
  const stopSide = bit(flag, 1).mul(span(across, float(0), halfW.sub(stopInset), fwA))
    .add(bit(flag, 2).mul(span(across, halfW.negate().add(stopInset), float(0), fwA)));
  const stop = span(along, float(stopLine[0]), float(stopLine[1]), fwL).mul(stopSide)
    .mul(giveWayStyle === 'stop' ? jZebra.add(jSignal).add(jGive) : jZebra.add(jSignal));
  // (giveWay 'teeth': German Haifischzähne, white triangles 0.5 m at the base and 0.6 m deep pointing at the driver)
  const tu = fract(across.div(0.75)).sub(0.5).abs().mul(0.75);
  const tt = along.sub(0.5).div(0.6);
  const teeth = giveWayStyle !== 'teeth' ? float(0) : clamp(float(0.25).mul(float(1).sub(tt)).sub(tu).div(fwA).add(0.5), 0, 1).mul(span(along, float(0.5), float(1.1), fwL));
  const giveWay = giveWayStyle === 'stop' ? float(0) : (giveWayStyle === 'teeth' ? teeth : max(line(along, float(0.8), float(0.2), fwL), line(along, float(1.3), float(0.2), fwL))
    .mul(pulses(across.add(0.3), float(0.9), float(0.6), fwA))).mul(stopSide).mul(jGive);
  const SD = { at: [0.7, 3.9], w: 0.12, period: 0.6, on: 0.3, ...(ZB.studs ?? {}) };
  const studs = max(line(along, float(SD.at[0]), float(SD.w), fwL), line(along, float(SD.at[1]), float(SD.w), fwL))
    .mul(pulses(across, float(SD.period), float(SD.on), fwA)).mul(span(across, halfW.negate().add(0.3), halfW.sub(0.3), fwA)).mul(ZB.atSignals ? 0 : jSignal);
  // centre and edge lines carry on past the stop line
  const beyond = span(along, float(stopLine[0]), float(Math.max(6.5, stopLine[1] + 0.8)), fwL);
  const crossWhite = clamp(zebra.add(stop).add(giveWay).add(studs).add(edgeR.add(edgeL).mul(edgeOn).mul(beyond)), 0, 1);
  const crossYellow = twoWay.mul(dbl).mul(beyond);

  // ---- sidewalks: d = metres from the kerb outwards, sw = sidewalk width
  const d = abs(across).sub(halfW);
  const sw = flag.div(10);
  const kerb = span(d, float(0), float(SW.kerbW), fwA);
  // (with a gutter: the kerb's arris, a thin shade line along its road-side edge)
  const arris = SW.gutter ? span(d, float(0), float(0.035), fwA) : float(0);
  const sideStain = fbm(vec2(d.mul(0.5), along.div(3)), fwL.div(3), 3, 131);
  const sideTone = hashI(floor(along.div(120)), floor(abs(across).div(40)), 137);     // blocks of different paving
  const paveBase = mix(vec3(...SW.paving), vec3(0.3, 0.2, 0.16), f01(sideTone.greaterThan(1 - SW.red)));  // grey or brick red
  let paving;
  if (SW.flag) {
    const fa = float(SW.flag[0]), fb = float(SW.flag[1]);
    const pavers = hash2(floor(vec2(d.div(fa), along.div(fb).add(floor(d.div(fa)).mul(0.5)))), 127);
    const paverJ = max(pulses(d, fa, float(0.015), fwA), pulses(along.add(floor(d.div(fa)).mul(fa)), fb, float(0.015), fwL));
    paving = paveBase.mul(mix(float(1), pavers.mul(0.16).add(0.92), resolved(fwA.div(fa))))
      .mul(float(1).sub(paverJ.mul(0.3))).mul(sideStain.sub(0.5).mul(0.35).add(1));
  } else {
    // poured asphalt: fine grain, patches where it was dug up (lighter or darker rectangles), a block's tone
    const grain = mix(float(0.5), vnoise(vec2(d, along).div(0.07), 133), resolved(max(fwA, fwL).div(0.07)));
    const dug = f01(hashI(floor(along.div(9)), floor(d.div(2.5)), 135).lessThan(0.07)).mul(resolved(max(fwA, fwL).div(2)));
    paving = paveBase.mul(grain.sub(0.5).mul(0.14).add(1)).mul(sideStain.sub(0.5).mul(0.28).add(1))
      .mul(sideTone.mul(0.1).add(0.95)).mul(mix(float(1), float(0.86), dug));
  }
  // (style2: 06b's sidewalk style 1, the Berliner Gehweg: Mosaikpflaster under and over the walkway (kerb side, house
  // side), the walkway of large granite slabs or 35 cm concrete plates by block)
  let style2Paving = null;
  if (SW.style2) style2Paving = () => {
    const S2 = { mosaic: [0.27, 0.264, 0.255], slab: [0.36, 0.35, 0.33], plate: [0.31, 0.305, 0.295], granite: 0.5,
      slabSize: [1.0, 1.5], under: [0.28, 0.5, 2.0], over: [0.12, 0.3, 0.8], ...SW.style2 };
    const uW = clamp(sw.mul(S2.under[0]), S2.under[1], S2.under[2]), oW = clamp(sw.mul(S2.over[0]), S2.over[1], S2.over[2]);
    const wa = float(SW.kerbW).add(uW), wb = sw.sub(oW);
    // mosaic: 6 cm setts of mixed granite (grey, pink, dark) with sandy joints; a mottled mean far off
    const mcell = floor(vec2(d.div(0.06), along.div(0.06)));
    const mh = hash2(mcell, 177);
    const mres = resolved(max(fwA, fwL).div(0.06));
    const mTone = mix(vec3(...S2.mosaic), mix(vec3(0.26, 0.22, 0.2), vec3(0.13, 0.13, 0.13), f01(mh.greaterThan(0.5))), f01(abs(mh.sub(0.5)).greaterThan(0.36)).mul(0.45));
    const mJ = max(pulses(d, float(0.06), float(0.012), fwA), pulses(along, float(0.06), float(0.012), fwL));
    const mosaic = mix(vec3(...S2.mosaic), mTone.mul(float(1).sub(mJ.mul(0.25))).mul(mh.mul(0.16).add(0.92)), mres)
      .mul(sideStain.sub(0.5).mul(0.35).add(1));
    // walkway: granite slabs (the Charlottenburger Platten) or concrete plates per 60 m block
    const gran = f01(hashI(floor(along.div(60)), floor(abs(across).div(40)), 179).lessThan(S2.granite));
    const sa = mix(float(0.35), float(S2.slabSize[0]), gran), sb = mix(float(0.35), float(S2.slabSize[1]), gran);
    const wd = d.sub(wa);
    const sRow = floor(wd.div(sa));
    const sl = hash2(floor(vec2(wd.div(sa), along.div(sb).add(sRow.mul(0.5)))), 181);
    const sJ = max(pulses(wd, sa, float(0.01), fwA), pulses(along.add(sRow.mul(sb).mul(0.5)), sb, float(0.01), fwL));
    const walkway = mix(vec3(...S2.plate), vec3(...S2.slab), gran)
      .mul(mix(float(1), sl.mul(0.14).add(0.93), resolved(fwA.div(sa)))).mul(float(1).sub(sJ.mul(0.35)))
      .mul(sideStain.sub(0.5).mul(0.3).add(1));
    const inWalk = span(d, wa, wb, fwA);
    return mix(mosaic, walkway, inWalk);
  };
  // (promenade: 06b's sidewalk style 2, [markings] promenades: a water-bound gravel walk (buff, mottled, darker in
  // wheel-worn and puddled patches) with a granite edging along the kerb side; city.json markings.sidewalk.promenade
  // { gravel: [dark, light] linear, edge: m }; off by default)
  let promPaving = null;
  if (SW.promenade) promPaving = () => {
    const PR = { gravel: [[0.3, 0.265, 0.2], [0.4, 0.355, 0.27]], edge: 0.35, ...SW.promenade };
    const g = fbm(P.div(2.5), fwP.div(2.5), 3, 191), big = fbm(P.div(17), fwP.div(17), 2, 193);
    const grit = mix(float(0.5), hash2(floor(P.div(0.05)), 195), resolved(fwP.div(0.05)));
    const gravel = mix(vec3(...PR.gravel[0]), vec3(...PR.gravel[1]), g).mul(big.sub(0.5).mul(0.3).add(1)).mul(grit.sub(0.5).mul(0.12).add(1));
    const edging = vec3(0.3, 0.295, 0.285).mul(float(1).sub(pulses(along, float(1), float(0.012), fwL).mul(0.4)));
    return mix(gravel, edging, span(d, float(SW.kerbW), float(SW.kerbW + PR.edge), fwA));
  };
  // kerbstones: 1 m granite blocks, speckled, a dark joint between them
  const kerbTone = hashI(floor(along), float(0), 141).mul(0.08).add(0.96);
  const speck = SW.granite ? mix(float(0.5), vnoise(vec2(d, along).div(0.03), 143), resolved(max(fwA, fwL).div(0.03))).sub(0.5).mul(0.3).add(1) : float(1);
  const kerbCol = vec3(...SW.kerb).mul(kerbTone).mul(speck).mul(float(1).sub(pulses(along, float(1), float(0.012), fwL).mul(0.4)));
  const pits = f01(sw.greaterThan(2.9)).mul(span(d, float(0.5), float(1.7), fwA))
    .mul(pulses(along, float(8), float(1.2), fwL)).mul(SW.pits ? 1 : 0);
  const pitCol = mix(vec3(0.05, 0.04, 0.03), vec3(0.05, 0.09, 0.03), hashI(floor(along.div(8)), floor(across), 139));
  const bike = f01(sw.greaterThan(4.4)).mul(span(d, float(2.1), float(3.6), fwA)).mul(SW.bike ? 1 : 0);
  const bikeCol = vec3(...(SW.bike ?? [0, 0, 0])).mul(grainK);
  const tactile = f01(sw.greaterThan(1.9)).mul(span(d, sw.sub(1.05), sw.sub(0.75), fwA)).mul(SW.tactile ? 1 : 0);
  // (kerbTop: the kerb's flamed top face lit brighter than the paving, as on the City's granite; 1: as the kerb colour)
  const sideFrom = (pav) => {
    let sd = mix(mix(pav, kerbCol.mul(SW.kerbTop ?? 1), kerb), kerbCol.mul(SW.arrisShade ?? 0.55), arris);
    sd = mix(sd, pitCol, pits);
    sd = mix(sd, bikeCol, bike);
    return mix(sd, vec3(0.55, 0.4, 0.06).mul(paintK), tactile);
  };
  const side = sideFrom(paving);

  // ---- medians: kerbs and a clipped hedge, with bougainvillea flowering in places
  const hedgeN = fbm(vec2(d.div(0.8), along.div(1.5)), fwL.div(1.5), 3, 149);
  // flowers in scattered clusters of small dots, not solid blobs
  const dots = mix(float(0.35), f01(hash2(floor(vec2(d.div(0.25), along.div(0.25))), 153).greaterThan(0.55)),
    resolved(fwL.div(0.25)));
  const bloom = smoothstep(0.62, 0.74, fbm(vec2(d.div(2), along.div(4)), fwL.div(4), 3, 151)).mul(dots).mul(SW.flowers ? 1 : 0);
  // (sidewalk.median [[dark rgb], [light rgb]]: the median's planting; Berlin's are mown grass under trees, not a
  // clipped hedge, and the default's saturated green read as neon)
  const MD = SW.median ?? [[0.03, 0.065, 0.02], [0.075, 0.12, 0.035]];
  const hedge = mix(vec3(...MD[0]), vec3(...MD[1]), hedgeN);
  const medianCol = mix(mix(hedge, vec3(0.3, 0.07, 0.15).mul(hedgeN.add(0.5)), bloom.mul(0.7)), vec3(0.46, 0.45, 0.43),
    max(span(d, float(0), float(0.2), fwA), span(d, sw.sub(0.2), sw, fwA)));

  // ---- runways: along 0..L, e = distance from the nearer threshold, r = |across|
  const L = code.mul(20);
  const e = min(along, L.sub(along));
  const r = abs(across);
  const rw = halfW;
  const rwEdge = span(r, rw.sub(1.5), rw.sub(0.6), fwA);
  const rwCentre = line(across, float(0), float(0.9), fwA).mul(pulses(along, float(50), float(30), fwL))
    .mul(f01(e.greaterThan(70)));
  // threshold: 4 m stripes 1.8 m wide from 6 to 36 m, leaving the middle 3.6 m clear
  const piano = span(e, float(6), float(36), fwL).mul(pulses(r.sub(1.8), float(3.6), float(1.8), fwA))
    .mul(span(r, float(1.8), rw.sub(3), fwA));
  // aiming point at 400 m and touchdown zone bars every 150 m to 900 m
  const aiming = span(e, float(400), float(445), fwL).mul(span(r, float(9), float(19), fwA));
  const tdzAt = f01(e.greaterThan(140).and(e.lessThan(930)).and(abs(e.sub(420)).greaterThan(40)));
  const tdz = tdzAt.mul(pulses(e, float(150), float(22.5), fwL)).mul(span(r, float(9), float(19), fwA))
    .mul(pulses(r.sub(9), float(4.5), float(3), fwA));
  // rubber deposits where wheels touch down, streaked along the runway
  const rubber = smoothstep(250, 400, e).mul(below(600, 1000, e)).mul(below(4, 14, r))
    .mul(fbm(vec2(across.div(1.5), along.div(40)), fwL.div(40), 3, 157).mul(1.2));
  const rwSurface = vec3(0.19, 0.19, 0.185).mul(grainK).mul(float(1).sub(rubber.mul(0.75)));
  const rwPaint = clamp(rwEdge.add(rwCentre).add(piano).add(aiming).add(tdz), 0, 1);
  const runway = mix(rwSurface, WHITE.mul(1.1).mul(paintK), rwPaint.mul(0.95));

  // ---- pedestrian streets: large stone slabs
  const slab = hash2(floor(vec2(across.div(0.9), along.div(0.9))), 163);
  const plaza = mix(vec3(0.36, 0.34, 0.31), vec3(0.42, 0.4, 0.36), mix(float(0.5), slab, resolved(fwA.div(0.9))))
    .mul(float(1).sub(max(pulses(across, float(0.9), float(0.02), fwA), pulses(along, float(0.9), float(0.02), fwL)).mul(0.3)))
    .mul(sideStain.sub(0.5).mul(0.3).add(1));

  // ---- UK zebra crossings between junctions (type 6; along 20 at the crossing's middle): stripes 0.6 m on
  // 0.6 m off across the road over 3 m, a black stripe against each kerb; a give-way line of 0.5 m dashes 1.1 m
  // before them each side; then white zig-zags (2 m units between guide lines 0.5 m apart) along both kerbs and,
  // on two-way roads, down the middle
  const u = along.sub(20), au = abs(u);
  const ZM = { half: 1.5, period: 1.2, bar: 0.6, give: true, ...(ZB.mid ?? {}) };
  const zStripes = span(au, float(-1), float(ZM.half), fwL).mul(pulses(across.add(halfW).sub(ZM.period * 0.75), float(ZM.period), float(ZM.bar), fwA))
    .mul(span(across, halfW.negate().add(0.6), halfW.sub(0.6), fwA));
  const zGive = line(au, float(2.6), float(0.2), fwL).mul(pulses(across, float(1), float(0.5), fwA))
    .mul(span(across, halfW.negate().add(0.3), halfW.sub(0.3), fwA)).mul(ZM.give ? 1 : 0);
  const tri = abs(fract(u.div(2)).sub(0.5)).mul(2);
  const zigAt = (o, c) => line(o, tri.sub(0.5).mul(0.5).add(c), float(0.1), fwA);
  // (centre zig-zags only where the road has a centre line: two-way, lanes marked, centreZigMin m wide or more)
  const zigs = max(max(zigAt(toL, 0.55), zigAt(toR, 0.55)), zigAt(across, 0).mul(twoWay).mul(f01(halfW.mul(2).greaterThan(ZB.centreZigMin ?? 0))))
    .mul(f01(au.greaterThan(3.0))).mul(ZB.zigzags === false ? 0 : 1);
  // signal-controlled crossings between junctions (flag 1, 06b_markings' pelicans, puffins and toucans): no stripes or
  // give-way line; two broken stud lines 2.4 m apart (TSRGD 1055.1) and a solid stop line 1.7 m back on each approach
  // half (the nearside's: left of the traffic's way when driving on the left)
  const sigX = bit(flag, 1).mul(tZebra);
  const SG = { studs: 1.2, w: 0.1, period: 0.5, on: 0.12, stop: 2.95, stopW: 0.3, ...(ZB.signal ?? {}) };
  const sStuds = line(au, float(SG.studs), float(SG.w), fwL).mul(pulses(across, float(SG.period), float(SG.on), fwA))
    .mul(span(across, halfW.negate().add(0.3), halfW.sub(0.3), fwA));
  const approachHalf = sel(u.lessThan(0), nearside === 'left' ? f01(across.greaterThan(0)) : f01(across.lessThan(0)),
    nearside === 'left' ? f01(across.lessThan(0)) : f01(across.greaterThan(0)));
  const sStop = line(au, float(SG.stop), float(SG.stopW), fwL).mul(span(across, halfW.negate().add(0.3), halfW.sub(0.3), fwA))
    .mul(mix(approachHalf, f01(u.lessThan(0)), oneway));
  const zebraWhite = clamp(mix(zStripes.add(zGive), sStuds.add(sStop), sigX).add(zigs), 0, 1);
  const zebraCol = mix(asphalt, WHITE.mul(paintK), zebraWhite);
  // ---- Belisha beacons (type 7; along = metres above the pavement): black-and-white banded pole, amber globe
  const bandsB = f01(fract(along.div(0.6)).lessThan(0.5)).mul(f01(along.greaterThan(0.25)));
  const globe = f01(along.greaterThan(2.76)).mul(tBeacon);
  const beaconCol = mix(mix(vec3(0.02, 0.02, 0.02), vec3(0.62, 0.62, 0.6), bandsB), vec3(0.85, 0.42, 0.04), globe);

  // ---- tram tracks (type 8; b the bed: 0 asphalt, 1 setts, 2 grass, 3 ballast): two grooved rails 1.435 m apart,
  // their steel heads 7 cm wide with the groove on the gauge side, a dark bitumen seal along each in the asphalt
  // (built only where city.json has markings.tram: every branch costs every markings fragment)
  const tramBuild = () => {
    const TR = { rail: [0.42, 0.41, 0.4], groove: [0.03, 0.028, 0.026], ballast: [0.15, 0.135, 0.12], sleeper: [0.3, 0.295, 0.28],
      grass: [0.05, 0.08, 0.03], ...(tramOpt ?? {}) };
    const ra = abs(across);
    const bed = code;
    const tramAsph = ROAD_MINOR.mul(grainK).mul(float(1).sub(span(ra, float(0.6), float(0.9), fwA).mul(0.25)));
    const tramSetts = settsHere();
    const tramGrass = vec3(...TR.grass).mul(mix(float(0.5), vnoise(vec2(across.div(0.4), along.div(0.6)), 183), resolved(fwL.div(0.6))).mul(0.6).add(0.7));
    const sleepers = pulses(along, float(0.65), float(0.24), fwL).mul(span(ra, float(0), float(1.3), fwA));
    const tramBallast = mix(vec3(...TR.ballast).mul(mix(float(1), hash2(floor(vec2(across, along).div(0.05)), 185).mul(0.4).add(0.8), resolved(fwL.div(0.05)))),
      vec3(...TR.sleeper), sleepers);
    const tramBed = sel(bed.lessThan(0.5), tramAsph, sel(bed.lessThan(1.5), tramSetts, sel(bed.lessThan(2.5), tramGrass, tramBallast)));
    const railHead = span(ra, float(0.7175), float(0.7875), fwA);
    const groove = span(ra, float(0.68), float(0.7175), fwA).mul(f01(bed.lessThan(1.5)));
    return mix(mix(tramBed, vec3(...TR.groove), groove), vec3(...TR.rail), railHead);
  };

  const roadCol = mix(mix(mix(asphalt, WHITE.mul(paintK), whiteLanes), CENTRE.mul(paintK), yellowLanes), kerbLineCol.mul(paintK), kerbPaint);
  const crossCol = mix(mix(mix(asphalt, WHITE.mul(paintK), crossWhite), CENTRE.mul(paintK), crossYellow), kerbLineCol.mul(paintK), kerbPaint);
  const baseCol = roadCol.mul(tLanes).add(crossCol.mul(tCross)).add(side.mul(tSide)).add(medianCol.mul(tMedian))
    .add(runway.mul(tRunway)).add(plaza.mul(tPlaza)).add(zebraCol.mul(tZebra)).add(beaconCol.mul(tBeacon));
  // the new surfaces (Berlin M5), each in a branch taken by its own strips only (a strip's type is the same over it)
  m.colorNode = !(useSetts || tramOpt || style2Paving || promPaving || busLegend) ? baseCol : Fn(() => {
    const col = baseCol.toVar();
    if (useSetts) If(isSetts.greaterThan(0.5), () => { col.assign(mix(settsHere(), WHITE.mul(paintK), crossWhite.mul(tCross))); });
    if (tramOpt) If(tTram.greaterThan(0.5), () => { col.assign(tramBuild()); });
    if (style2Paving) If(tSide.greaterThan(0.5).and(code.greaterThan(0.5)).and(code.lessThan(1.5)), () => { col.assign(sideFrom(style2Paving())); });
    if (promPaving) If(tSide.greaterThan(0.5).and(code.greaterThan(1.5)), () => { col.assign(sideFrom(promPaving())); });
    if (busLegend) If(tLanes.greaterThan(0.5).and(bit(flag, 2).add(bit(flag, 4)).greaterThan(0.5)), () => {
      col.assign(mix(col, WHITE.mul(paintK), busLegend())); });
    return col;
  })();
  const paint = max(max(max(whiteLanes, yellowLanes), kerbPaint).mul(tLanes), max(max(crossWhite, crossYellow), kerbPaint).mul(tCross))
    .add(zebraWhite.mul(tZebra));
  m.roughnessNode = mix(float(0.9), float(0.65), paint).sub(inPatch.mul(tLanes).mul(0.05)).sub(tTram.mul(tramOpt ? 0.3 : 0));
  m.userData.nodes = { asphalt, whiteLanes, yellowLanes, side, runway };
  // (zebra.globeGlow: the Belisha beacons' amber globes lit from inside by day too, linear; 0: unlit)
  if (ZB.globeGlow) m.emissiveNode = vec3(1, 0.5, 0.06).mul(float(ZB.globeGlow)).mul(globe);

  // ---- street lamps (after dark only): posts on both kerbs, 0.5 m out, every 36 m facing each other on the big roads,
  // every 30 m staggered on small ones (both periods divide 06b_markings.py's along wrap). Sidewalks,
  // medians and crossings are in the same (across, along) frame as their carriageway, so they share its
  // pools; pedestrian streets get their own posts along their edges
  if (night) {
    const period = mix(float(30), float(36), big);
    const pole = halfW.add(0.5);
    let light = lampRow(across.sub(pole), along, period, float(0), fwL)
      .add(lampRow(across.add(pole), along, period, mix(float(0.5), float(0), big), fwL));
    // (city.json ground.plazaLamps { h, period, k }, default none (Singapore M8 fix round 1: promenades and park paths lit
    // evenly end to end): pedestrian streets under low lamps of that height, staggered `period` m apart along both
    // edges, so they lie in pools with dimmer stretches between, times k)
    if (PLAZA_LAMPS) {
      const PL = PLAZA_LAMPS, pp = float(PL.period), pole2 = halfW.add(0.3);
      const foot = lampRowH(across.sub(pole2), along, pp, float(0), fwL, PL.h).add(lampRowH(across.add(pole2), along, pp, float(0.5), fwL, PL.h));
      light = mix(light, foot.mul(PL.k), tPlaza);
    }
    const lampCol = mix(regionLamp(big, motorway, sodium), WARM_LED, tPlaza);
    // the lamp heads themselves, seen from far above once a road is a line a few pixels wide: their glare
    // averaged over the road (a 0.4 m2 lens at some 60 times the lit road's brightness, every period m on each side)
    const heads = float(1).sub(resolved(fwL.div(period), 3)).mul(float(2 * 0.4 * 60).div(period.mul(halfW.mul(2).max(4))))
      .mul(tLanes.add(tCross));
    // runways: edge lights every 60 m and centreline lights every 30 m, kept a couple of pixels across
    const spot = (x, y, p) => {
      const rr = max(float(0.35), max(fwA, fwL).mul(1.2));
      const dl = fract(y.div(p)).sub(0.5).mul(p);
      return float(1).sub(smoothstep(rr.mul(0.5), rr, vec2(x, dl).length()));
    };
    // (from afar, once the lights are under a pixel, their mean: a few dots on dark asphalt, not white bars)
    const rwLights = max(spot(r.sub(rw).add(1), along, 60), spot(across, along.add(15), 30).mul(f01(e.greaterThan(70))))
      .mul(tRunway).mul(2).mul(mix(float(0.08), float(1), resolved(fwL.div(2))));
    // (sidewalks, pale and right under the posts, get a little less: they read as white bands otherwise)
    // (pedestrian plazas too: pale stone wholly inside the pools glowed as flat white slabs)
    const onSurface = light.mul(float(1).sub(tRunway)).mul(float(1).sub(tSide.mul(0.6))).mul(float(1).sub(tPlaza.mul(0.6)));
    let lit = m.colorNode.mul(onSurface).mul(STREET).add(heads.mul(LAMP_HEADS)).mul(lampCol).mul(PROC())
      .add(vec3(0.95, 0.95, 1).mul(rwLights));
    // (ground.litAreas: pavements and plazas get all of it, the carriageway a share)
    if (LIT_AREAS) lit = lit.add(m.colorNode.mul(litAreas()).mul(mix(float(LIT_ROADS), float(1), max(tSide, tPlaza))));
    night.withLights(m, lit);
  }
  return m;
}

// Intertidal mudflats (such as Shenzhen Bay's off Futian and Houhai): grey-brown silt, darker and glossy where
// wet, cut by dendritic tidal creeks that hold water, with algae-green film and lighter drier crests.
function mudMaterial() {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.6, metalness: 0 });
  // creeks: the zero set of a domain-warped noise field makes meandering, branching channels
  const warp = vec2(fbm(P.div(90), fwP.div(90), 3, 81), fbm(P.div(90).add(17.3), fwP.div(90), 3, 83)).sub(0.5).mul(60);
  const Q = P.add(warp);
  const n1 = fbm(Q.div(140), fwP.div(140), 4, 85).sub(0.5);
  const n2 = fbm(Q.div(45), fwP.div(45), 3, 87).sub(0.5);
  const creekBig = below(float(0.006), float(0.016).add(fwP.div(140)), abs(n1));
  const creekSmall = below(float(0.004), float(0.012).add(fwP.div(45)), abs(n2)).mul(smoothstep(0.02, 0.08, abs(n1)).oneMinus().mul(0.4).add(0.6));
  const creek = max(creekBig, creekSmall.mul(0.8));
  // moisture: wetter near creeks, drier ridges between; fine ripple texture where resolved
  const wet = max(creek, below(float(0.02), float(0.09), abs(n1)).mul(0.45)).add(fbm(P.div(12), fwP.div(12), 2, 89).sub(0.5).mul(0.2)).clamp(0, 1);
  const ripple = mix(float(0.5), vnoise(P.div(0.6), 91), resolved(fwP.div(0.6)));
  const silt = mix(vec3(0.17, 0.155, 0.13), vec3(0.125, 0.115, 0.1), wet).mul(ripple.mul(0.16).add(0.92));
  const algae = smoothstep(0.55, 0.8, fbm(P.div(35), fwP.div(35), 3, 93)).mul(wet).mul(0.55);
  const surface = mix(silt, vec3(0.05, 0.065, 0.04), algae);
  const channel = vec3(0.1, 0.115, 0.12);                     // standing water in the creeks, lit by the sky
  m.colorNode = mix(surface, channel, creek);
  m.roughnessNode = mix(mix(float(0.85), float(0.35), wet), float(0.08), creek);
  return m;
}

// Gravel (05_ground's gravel layer): compacted "stabilisé" of French formal gardens (the Tuileries' and the
// Luxembourg's allées) and loose-surfaced pedestrian areas. Two tones (city.json ground.gravel, sRGB hex),
// one per 400 m cell so neighbouring gardens differ, with rake marks, grain and a darker, trodden middle
// where the fine grain resolves; puddle-dark patches after rain are left out (October afternoon, dry)
function gravelMaterial(night, tones = ['#cdc4b7', '#ddd9d1']) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.96, metalness: 0 });
  const [a, b] = tones.map((h) => new THREE.Color(h));        // THREE.Color from hex is linear already
  const pick = hash2(floor(P.div(400)), 201);
  // gravel in the sun reads a little darker than its swatch (shadowed grains between the lit ones)
  const base = mix(vec3(a.r, a.g, a.b), vec3(b.r, b.g, b.b), pick).mul(0.62);
  const grain = mix(float(0.5), hash2(floor(P.div(0.15)), 203), resolved(fwP.div(0.15)));
  const stain = fbm(P.div(7), fwP.div(7), 3, 205);
  const trodden = fbm(P.div(40), fwP.div(40), 2, 207);
  let col = base.mul(grain.sub(0.5).mul(0.12).add(1)).mul(stain.sub(0.5).mul(0.22).add(1))
    .mul(trodden.sub(0.5).mul(0.14).add(1));
  // weeds and moss at the edges of little-used corners
  col = mix(col, vec3(0.12, 0.13, 0.07), smoothstep(0.78, 0.9, fbm(P.div(18), fwP.div(18), 2, 209)).mul(0.35));
  m.colorNode = col;
  if (night) night.withLights(m, col.mul(yardLamps(30, 0.3, 0.03)));
  return m;
}

// Paved squares and parvis (05_ground's paved layer: stone pedestrian areas): pale limestone and granite, in
// courses of large slabs (Notre-Dame's parvis, the Hôtel de Ville's square) or small setts (the Sacré-Cœur's),
// one kind per 150 m cell, the slabs' tone varying stone by stone, stains and wear; their mean from afar.
// tones: [pale, darker] sRGB hex (city.json ground.paved; Paris's pale slabs at the Étoile #d4cec4, the
// darker ring #969191)
// (city.json ground.pavedStyle, optional: setts, the share of cells in small setts (0.35); slab [w, d] m; joints, how
// dark the joints are (0.35); mottle, low-frequency tone variation over tens of metres (0); cellTone, how far each 150 m
// cell's tone leans to the darker colour (0.35; 0: one tone, the slabs' own variation only))
function pavedMaterial(night, tones = ['#c9c3b8', '#8f8a84'], style = {}) {
  const ST = { setts: 0.35, slab: [1.2, 0.8], joints: 0.35, mottle: 0, cellTone: 0.35, ...style };
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.85, metalness: 0 });
  const [a, b] = tones.map((h) => new THREE.Color(h));
  const cell = floor(P.div(150));
  const kind = hash2(cell, 211);
  const setts = f01(kind.lessThan(ST.setts));                   // a third small setts, the rest slabs
  const base = mix(vec3(a.r, a.g, a.b), vec3(b.r, b.g, b.b), hash2(cell, 213).mul(ST.cellTone).add(setts.mul(0.35))).mul(0.62);
  // slabs 1.2 x 0.8 m in running bond; setts 0.14 m
  const sz = mix(vec2(...ST.slab), vec2(0.14, 0.14), setts);
  const row = floor(P.y.div(sz.y));
  const q = vec2(P.x.div(sz.x).add(row.mul(0.5)), P.y.div(sz.y));
  const stone = mix(float(0.5), hash2(floor(q), 215), resolved(fwP.div(sz.y)));
  const joints = max(pulses(q.x, float(1), float(0.03), fwP.div(sz.x)), pulses(q.y, float(1), float(0.03), fwP.div(sz.y)));
  const stain = fbm(P.div(6), fwP.div(6), 3, 217);
  const wear = fbm(P.div(35), fwP.div(35), 2, 219);
  const col = base.mul(stone.sub(0.5).mul(mix(float(0.16), float(0.3), setts)).add(1))
    .mul(float(1).sub(joints.mul(ST.joints))).mul(stain.sub(0.5).mul(0.25).add(1)).mul(wear.sub(0.5).mul(0.12).add(1))
    .mul(fbm(P.div(22), fwP.div(22), 3, 223).sub(0.5).mul(ST.mottle).add(1));
  m.colorNode = col;
  m.roughnessNode = float(0.85);
  if (night) night.withLights(m, col.mul(LIT_AREAS ? yardLamps(26, 0.4, 0.04).add(litAreas()) : yardLamps(26, 0.4, 0.04)));
  return m;
}
// asphalt pedestrian areas (05_ground's asphalt layer: many of Paris's squares and sidewalks mapped as areas):
// the minor roads' asphalt, a little paler (no traffic polish), same grain
function asphaltAreaMaterial(night) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.9, metalness: 0 });
  const col = ROAD_MINOR.mul(1.12).mul(asphaltFactor()).mul(fbm(P.div(12), fwP.div(12), 2, 221).sub(0.5).mul(0.2).add(1));
  m.colorNode = col;
  if (night) night.withLights(m, col.mul(LIT_AREAS ? yardLamps(24, 0.4, 0.04).add(litAreas()) : yardLamps(24, 0.4, 0.04)));
  return m;
}

// The land beyond the ground area, out to 30-40 km (05a_terrain.py's backdrop): vertex colours (forest on
// the hills, towns and fields on the flats, dark lakes) with a little large-scale mottling. Nothing below
// the sea plane is drawn, so the coast is where the coarse surface dips under it. Its haze is the scene's
// (main.js), which far out thins with height, so the far hills (Shenzhen's 大帽山 and 梧桐山) still stand out
// against the sky.
// Where a vertex has the town's colour (tiles.json town.rgb, setTown) the town's roofscape pattern is drawn
// instead, so a town running across the ground area's edge goes on unbroken.
// cover (createGroundMaterials' area.cover): false for a city without land cover maps (tiles.json cover), whose
// COVER.on stays 0: only the vertex colours' path is built, none of the maps' (New York: 54,000 nodes and ~140 ms of
// node building per pass and light with both, 13,700 with its own). true or null: both, the uniform picks (the maps
// arrive after the first frame)
function backdropMaterial(night = null, cover = null) {
  const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.95, metalness: 0 });
  const mottle = fbm(P.div(900), fwP.div(900), 3, 171).sub(0.5).mul(0.35).add(1)
    .mul(fbm(P.div(140), fwP.div(140), 2, 173).sub(0.5).mul(0.2).add(1));
  const townRGB = uniform(new THREE.Color(0, 0, 0));
  const on = uniform(0);
  const vc = vertexColor().rgb;
  // built land: the town and the field colours (bright), not forest or lakes (dark). The fields are leafy
  // suburbs here: the town's roofscape under a share of canopy, not open green (New York has no farmland)
  const lum = dot(vc, vec3(0.2126, 0.7152, 0.0722));
  const built = smoothstep(float(0.08), float(0.13), lum).mul(on);
  const leafy = smoothstep(float(0.0), float(0.03), vc.g.sub(vc.r.add(vc.b).mul(0.5)));
  const dist = positionWorld.distance(cameraPosition);
  // the land cover maps (coverColour) instead of the vertex colours, whose vertices lie kilometres apart on the
  // flats, with detail of its own per class, 20-300 m, which the haze takes before it can alias (Paris M7:
  // the map alone read as blurred camouflage): field parcels (stubble, ploughland, winter wheat) on a grid
  // turned per 2 km, speckled towns, clumped woods
  const cc = coverColour();
  const isTown = float(1).sub(smoothstep(0.02, 0.06, cc.sub(townRGB).length()));
  const water = nearClass(cc, CLASS.water, 0.012);
  const wood = nearClass(cc, CLASS.wood).mul(float(1).sub(water)), field = nearClass(cc, CLASS.field, 0.07);
  const detailK = float(1).sub(smoothstep(float(9000), float(22000), dist));
  // (Paris M9: in branches, each built from copies of its inputs taken before them (the maps are looked up
  // there too, outside any branch): the vertex colours' towns only without the maps (a uniform), the towns'
  // roofscape only where there are towns, the maps' detail only within 22 km, the ground between the masses
  // only within 9 km of the camera and in towns. It was all evaluated, weighted by 0, on every pixel)
  const colour = Fn(() => {
    const V = Object.fromEntries(Object.entries({ p: P, fw: fwP, dist, vc, mottle, built, leafy,
      ...cover === false ? {} : { cc, isTown, water, wood, field, detailK } }).map(([k, n]) => [k, n.toVar()]));
    const out = vec3(0).toVar();
    const vertexColours = () => {
      out.assign(V.vc.mul(V.mottle));
      If(V.built.greaterThan(0), () => {
        const canopy = vec3(0.05, 0.068, 0.035).mul(fbm(V.p.div(30), V.fw.div(30), 2, 177).mul(0.5).add(0.75));
        const nearT = mix(townPattern(V.p, V.fw).col, canopy, V.leafy.mul(0.5).add(0.12));
        // far out the pattern's streets alias into furrows at grazing angles: its mean colour instead
        const far = mix(townRGB, vec3(0.05, 0.068, 0.035), V.leafy.mul(0.4).add(0.2)).mul(V.mottle);
        const suburb = mix(nearT, far, smoothstep(float(5000), float(9000), V.dist));
        out.assign(mix(out, suburb, V.built));
      });
    };
    const maps = () => {
      const shade = V.mottle.sub(1).mul(float(1).sub(V.water)).add(1);
      out.assign(V.cc.mul(shade));
      If(V.detailK.greaterThan(0), () => {
        const pc = floor(V.p.div(2000));
        const pa = hash2(pc, 351).mul(Math.PI / 2);
        const q = vec2(V.p.x.mul(cos(pa)).add(V.p.y.mul(sin(pa))), V.p.y.mul(cos(pa)).sub(V.p.x.mul(sin(pa)))).div(vec2(260, 150));
        const parcel = hash2(floor(q), 353);
        const parcelCol = mix(mix(vec3(0.2, 0.16, 0.11), vec3(0.26, 0.23, 0.16), hash2(floor(q), 355)), vec3(0.09, 0.12, 0.05),
          f01(parcel.lessThan(0.3)));
        const fieldK = V.field.mul(resolved(V.fw.div(150))).mul(V.detailK).mul(0.7);
        const speck = hash2(floor(V.p.div(28)), 357).sub(0.5).mul(0.45).mul(resolved(V.fw.div(28))).mul(V.isTown).mul(V.detailK);
        const clump = vnoise(V.p.div(22), 359).sub(0.5).mul(0.6).mul(resolved(V.fw.div(22))).mul(V.wood).mul(V.detailK);
        out.assign(mix(V.cc, parcelCol, fieldK).mul(speck.add(clump).add(1)).mul(shade));
      });
      If(COVER_WATER_ON.mul(V.water).greaterThan(0), () => { out.assign(mix(out, COVER_WATER, V.water)); });
      // its towns near the camera: the ground between buildings as the town layer draws it under the masses
      // (calmTown), the cover's town colour from further (as the town layer fades to it)
      const townK = V.isTown.mul(float(1).sub(smoothstep(float(5000), float(9000), V.dist)));
      If(TOWN_TINT_ON.mul(V.isTown).greaterThan(0), () => { out.assign(mix(out, out.mul(TOWN_TINT), V.isTown.mul(float(1).sub(townK)))); });
      If(townK.greaterThan(0), () => { out.assign(mix(out, calmTown(V.cc, V.p, V.fw), townK)); });
    };
    if (cover === false) vertexColours();
    else If(COVER.on.lessThan(0.5), vertexColours).Else(maps);
    return out;
  })();
  m.colorNode = rockFace(colour);
  // (without the maps: no water on it, mix(0.95, 0.4, 0); nor the sky in it below, nor any lights or wet look after dark)
  m.roughnessNode = cover === false ? float(0.95) : mix(float(0.95), float(0.4), water.mul(COVER.on));
  if (WATER_SKY && WATER_SKY_K && cover !== false) {
    const ndv = cameraPosition.sub(positionWorld).normalize().y.clamp(0, 1);
    const fresnel = float(1).sub(ndv).pow(5).mul(0.98).add(0.02);
    const k = water.mul(COVER.on).mul(COVER_WATER_ON).mul(WATER_SKY_U);
    m.colorNode = m.colorNode.mul(float(1).sub(fresnel.mul(k)));
    m.emissiveNode = WATER_SKY.mul(fresnel).mul(k);
  }
  m.userData.setTown = (rgb) => {
    if (!rgb) return;
    townRGB.value.setRGB(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, THREE.SRGBColorSpace);
    TOWN_RGB_REF.value.copy(townRGB.value);
    on.value = 1;
  };
  m.maskNode = positionWorld.y.greaterThan(-1);
  // after dark: the towns beyond the masses as scattered warm lights (street lamps and windows, 70 m apart,
  // a third of them), each kept at least about a pixel wide and dimmer as it grows, so the far towns stay
  // points of light over a dark land rather than a glowing sheet (Paris M7: pitch black past the masses)
  // (Paris M9: in a branch, towns only: the rest of the backdrop skips its four hashes)
  if (night && cover !== false) {
    // (Paris M9: a dotted carpet, 45 m apart, half the cells, over an even glow of their light: at 40-60 % of Paris's
    // intensity out to the horizon, the woods, fields and rivers dark between)
    const lights = Fn(() => {
      const k = isTown.mul(COVER.on).toVar(), p = P.toVar(), fw = fwP.toVar();
      const e = vec3(0).toVar();
      If(k.greaterThan(0), () => {
        const g = p.div(45), gi = floor(g);
        const jit = vec2(hashI(gi.x, gi.y, 361), hashI(gi.x, gi.y, 363)).mul(0.8).add(0.1);
        const d = fract(g).sub(jit).mul(45);
        const r = max(float(3), fw.mul(0.8));
        const dot01 = exp(dot(d, d).div(r.mul(r).negate())).mul(float(9).div(r.mul(r)));
        const here = f01(hashI(gi.x, gi.y, 365).lessThan(0.5));
        let col = mix(vec3(1, 0.5, 0.16), vec3(1, 0.72, 0.42), hashI(gi.x, gi.y, 367));
        if (TOWN_WHITE) col = mix(col, vec3(...TOWN_WHITE), f01(hashI(gi.x, gi.y, 369).lessThan(TOWN_LED ?? 0.5)));
        e.assign(col.mul(dot01.mul(here).add(STREET_GLOW.far)).mul(k).mul(TOWN_FAR_K));
      });
      if (TOWN_ROADS) {
        const R = TOWN_ROADS;
        const road = nearClass(cc, vec3(...R.rgb.map((v) => s2l(v / 255))), R.tol ?? 0.03).mul(COVER.on).toVar();
        If(road.greaterThan(0), () => {
          const cell = floor(p.div(1500));
          const tint = mix(vec3(...(R.white ?? [1, 0.86, 0.7])), SODIUM, f01(hashI(cell.x, cell.y, 379).lessThan(R.sodium ?? 0.3)));
          e.addAssign(tint.mul(road).mul(R.k ?? 0.05));
        });
      }
      return e;
    })();
    // the rivers and lakes of the land cover near black after dark (their smooth, glossy surface mirrored the night
    // sky's pale haze: lavender ribbons across the dark land)
    night.withNight(m, (lit) => {
      lit.emissiveNode = lights.mul(night.lights);
      const wet = water.mul(COVER.on);
      lit.colorNode = m.colorNode.mul(float(1).sub(wet.mul(0.85)));
      lit.roughnessNode = mix(m.roughnessNode, float(0.95), wet);
    });
  }
  return m;
}

// city.json ground.relief (default 0: off): the slopes of the backdrop, the town layer and the parks lit more
// strongly than the sun alone lights them, a hillshade over their colour from the mesh's own normals: the albedo
// times 1 + relief x (n.l - flat n.l) / flat n.l, kept within [0.7, 1.4]. Seen from the city, the gentle
// ridges round a basin (London's Norwood ridge, 2-3 degrees over a kilometre and a half) change the sun's light
// by a few per cent only and read as a flat painted map (London M7 fix round); photos show them by their
// shading and their woods.
function relief(m, sunDir, k) {
  const L = uniform(sunDir);
  const flat = max(L.y, 0.2);
  const shade = clamp(dot(normalWorld, L).sub(L.y).div(flat).mul(k).add(1), 0.7, 1.4);
  m.colorNode = m.colorNode.mul(shade);
}

// the land cover maps (06e_masses; tiles.json cover): outer over the backdrop, its inner over the masses' zone
export function setCover(tex, rect, innerTex = null, inner = null) {
  COVER.outer.value = tex;
  COVER.rect.value.set(rect.x0, rect.z0, rect.x1, rect.z1);
  if (innerTex && inner) {
    COVER.inner.value = innerTex;
    COVER.innerRect.value.set(inner.x0, inner.z0, inner.x1, inner.z1);
    COVER.innerOn.value = 1;
  } else COVER.inner.value = tex;
  COVER.on.value = 1;
}
// the line map (tiles.json cover.inner.lines), loaded after the colour maps
export function setCoverLines(tex) {
  LINES.map.value = tex;
  LINES.near.value = tex;
  LINES.size.value.set(tex.image.width, tex.image.height);
  LINES.on.value = 1;
}

// night: the uniforms from night.js (createNight().u), or null for streets that stay dark; ground and
// markings: city.json's sections (city.js has the defaults)
// area { cover, masses } (main.js, from tiles.json): whether the city has land cover maps and block masses (true or
// false), so the backdrop and the town layer build only what it uses; null (unknown): both, as before
export function createGroundMaterials(markingsIndex, { sunDir = new THREE.Vector3(-0.6, 0.53, 0.6), night = null, ground, markings, realLamps = null, waterSky = null,
  area = {} } = {}) {
  area = { cover: null, masses: null, ...area };
  REAL_LAMPS = realLamps;
  WATER_SKY = waterSky;
  WATER_SKY_K = ground?.coverWaterSky ?? 0;
  ASPHALT_MOTTLE = ground?.asphaltMottle ?? 1;
  WATER_SKY_U.value = WATER_SKY_K;
  TOWN_LED = ground?.townLights?.led ?? null;
  TOWN_WHITE = ground?.townLights?.white ?? null;
  TOWN_FAR_K = ground?.townLights?.farK ?? 1.6;
  TOWN_PAINTED_LIT = ground?.townLights?.painted ?? null;
  TOWN_ROADS = ground?.townLights?.roads ?? null;
  LAMP_HEADS = ground?.lampHeads ?? 0.35;
  LIT_AREAS = ground?.litAreas?.length ? ground.litAreas : null;
  LIT_ROADS = ground?.litAreasRoads ?? 0.3;
  if (ground?.townLights) { STREET_GLOW.gain.value = ground.townLights.gain ?? 0.12; STREET_GLOW.base.value = ground.townLights.base ?? 0.08; STREET_GLOW.far.value = ground.townLights.far ?? 0.004; }
  TOWN_FAR_COVER.value = ground?.townFarCover ?? 0;
  COVER_BLEND = ground?.coverBlend ?? 400;
  if (ground?.townLawn) TOWN_LAWN = ground.townLawn.map((c) => vec3(...c));
  TOWN_NOISE_GREEN = ground?.townNoiseGreen ?? 0.35;
  TOWN_MAP_NEAR = ground?.townMapNear ?? 0;
  if (ground?.townPaving) TOWN_PAVING = ground.townPaving.map((c) => vec3(...c));
  const CLN = ground?.coverLines;
  if (CLN) {
    if (CLN.asphalt) LINES.asphalt.value.setRGB(...CLN.asphalt);
    if (CLN.ballast) { LINES.ballast0.value.setRGB(...CLN.ballast[0]); LINES.ballast1.value.setRGB(...CLN.ballast[1]); }
    if (CLN.track) LINES.track.value.setRGB(...CLN.track);
    LINES.pitch = CLN.pitch ?? LINES.pitch; LINES.band = CLN.band ?? LINES.band;
  }
  if (ground?.townNearTint) TOWN_NEAR_TINT.value.setRGB(...ground.townNearTint);
  if (ground?.coverTownTint) { TOWN_TINT.value.setRGB(...ground.coverTownTint); TOWN_TINT_ON.value = 1; }
  if (ground?.coverWater) { COVER_WATER.value.setRGB(...ground.coverWater); COVER_WATER_ON.value = 1; }
  OUTER_LAMPS = ground?.outerLamps ? { gain: 1, tint: [1, 1, 1], ...ground.outerLamps } : null;
  const { airportHeading = 0, lawn = [[0.042, 0.07, 0.036], [0.08, 0.11, 0.055]], aeroway = [[0.34, 0.34, 0.325], [0.42, 0.415, 0.395]], sodium = { arterial: 0.4, street: 0.2 }, streetLight = 2.2, yardBase = 1, gravel, paved, pavedStyle, asphalt = null, urban = {}, lawnStyle } = ground ?? {};
  STREET = streetLight;
  YARD_BASE = yardBase;
  APRON = ground?.apronLights ?? null;
  PLAZA_LAMPS = ground?.plazaLamps ? { h: 4.5, period: 22, k: 1, ...ground.plazaLamps } : null;
  ASPHALT_K = asphalt;
  JUNCTION_POOLS = ground?.junctionPools ? { cell: 22, h: 8, k: 1, ...ground.junctionPools } : null;
  if (asphalt) {
    ROAD_MAJOR = vec3(...ROAD_MAJOR0.map((v, i) => v * asphalt[i]));
    ROAD_MINOR = vec3(...ROAD_MINOR0.map((v, i) => v * asphalt[i]));
  }
  const { centreColour = 'yellow', dashes = { street: [6, 2], arterial: [10, 4], motorway: [15, 6], centre: [10, 4] }, sidewalk = {}, zebra, stopLine, lineWidth, edgeLines, stopInset,
    bigCentre, kerbLines, busLane, cycleLane, nearside, repaving, giveWay, setts, tram } = markings ?? {};
  if (ground?.rock === false) ROCK.on = false;
  else if (Array.isArray(ground?.rock)) {
    ROCK.on = true; ROCK.cosFrom = Math.cos(ground.rock[0] * Math.PI / 180); ROCK.cosTo = Math.cos(ground.rock[1] * Math.PI / 180);
  }
  if (ground?.landFarCover) { LAND_FAR.on = true; LAND_FAR.from.value = ground.landFarCover[0]; LAND_FAR.to.value = ground.landFarCover[1]; }
  const out = { land: landMaterial(night, urban), town: townMaterial(night, area.masses), green: greenMaterial(sunDir, night, lawn, lawnStyle), aeroway: aerowayMaterial(night, airportHeading, aeroway),
                road: roadMaterial(night, sodium), bridge: bridgeMaterial(night, sodium), mud: mudMaterial(),
                backdrop: backdropMaterial(night, area.cover), gravel: gravelMaterial(night, gravel), paved: pavedMaterial(night, paved, pavedStyle),
                asphalt: asphaltAreaMaterial(night) };
  if (ground?.relief) for (const k of ['town', 'backdrop', 'green']) relief(out[k], sunDir, ground.relief);
  if (markingsIndex) out.markings = markingsMaterial(markingsIndex, night, { centreColour, dashes, sidewalk, zebra, stopLine, lineWidth, edgeLines, stopInset,
    bigCentre, kerbLines, busLane, cycleLane, nearside, repaving, giveWay, setts, tram }, sodium);
  return out;
}
