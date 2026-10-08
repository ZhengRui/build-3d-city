// The facade's pattern library: wall patterns too particular to be a core feature's settings, named by the
// architecture they draw, not by the city that first needed them (facade.js builds each into a city's shader only when
// one of its styles lists the pattern's key, styles.js). Each takes a wall-detail branch's copies of the facade's nodes
// (V) and returns its colour (or its mask and colour), built inside the branch that calls it: a node first built inside
// one branch is declared in that branch's scope only, so nothing here is shared between calls.
//
//   gruenderzeit  (gruenderzeit)   Gründerzeit stucco: string courses at every floor with their shadow, the cornice's
//                                  shadow and its profile (frieze with consoles, soffit, dentils, corona; a plain eave on
//                                  a stripped front), window surrounds, hoods and a pediment over the Beletage, sills
//   frenchBalcony (frenchBalconies) a stucco slab at the French door's foot (its railing: the near detail's)
//   pilasterStrips (pilasters)     pilasters every n bays
//   frieze        (frieze)         a frieze with a running motif under the cornice
//   ceramicTiles  (ceramicTiles)   glazed tiles, each its own shade, over a joint grid (Karl-Marx-Allee)
//   plattenbau    (plattenbau)     panel joints, loggia columns with coloured fronts, a darker plinth
//   slabEdges     (slabEdges)      white slab edges at every floor, coloured balcony panels (Hansaviertel)
//   stoneJoints   (stoneJoints)    ashlar joints (0.75 m courses, three slabs a bay), a recessed top floor on some
//   precastJoints (precast)        precast joints at the bays, lighter spandrel bands
//   buttresses    (buttresses)     buttresses at each bay's edge
//   pillaredPorch (porch)          a pale porch with two columns, the door and its fanlight, one bay in three
//   loadingDoors  (loadingDoors)   a column of timber doors one bay in three with iron platforms (dock warehouses)
//   tiledBands    (tileBands)      a tiled band facade: tile joints close up (227 x 60 mm, stretcher bond), the
//                                  spandrel bands in a second tile tone on some, a light slab edge at every floor
//                                  with its shadow (Japan's tiled mid-rise offices and mansions)
//   balconyRails  (balconyRails)   apartment balcony railings: a continuous balcony on every floor above the ground,
//                                  its front a frosted-glass, solid or barred railing panel, the slab edge, partition
//                                  boards between the flats, the shade under the balcony above (Japanese mansions)
//   timberFrame   (timberFrame)    timber posts at each bay's edges, a tie beam under the eaves and over the ground
//                                  floor, plaster panels between (temples and shrines: vermilion or dark timber)
//   lapSiding     (lapSiding)      horizontal siding boards (or mortar's trowel lines) close up, a small eave over
//                                  the ground floor's openings (low wooden houses)
//   signboardStack (signboards)    a stack of vertical signboards (袖看板) at one end of a narrow front, one box per
//                                  floor in its own colour with a column of glyphs, or one tall board; facade.js lays
//                                  it over the finished wall (mask and colour; lit after dark)
//   estateAccents (estateAccents)  public housing blocks: pastel paint with colour accents (end-bay stripes, a
//                                  crown band), a grey void-deck ground floor
//   bayWindows    (bayWindows)     tiled residential towers: projecting bay windows (lit ledge, its shadow, cheeks,
//                                  soffit)
//   shophouseBalconies (shophouseBalconies) Cantonese shophouses and walk-ups (tong lau): a balcony at every floor,
//                                  open, caged or glazed in, the slab's shadow, soot streaks, signboards on the
//                                  first floor
//   ribbonSpandrels (ribbonSpandrels) flatted factories: concrete spandrel bands between ribbon windows with rain
//                                  streaks, roller shutters on the ground floor
//   verandahArcade (verandahArcade) colonial verandahs: arches between piers on the lowest two floors, a cornice
//   tiledWall     (tiledWall)      a windowless wall clad in square ceramic tiles (0.3 m, each its own shade) over a joint
//                                  grid, a darker plinth and rain-darkened foot (the Hong Kong Cultural Centre's pink tiles)
// On the wall itself (no fade: they read from the air, box-filtered; c: the facade's own nodes, not a branch's copies):
//   paintBands    (paintBands)     accent paint over an off-white block: a top band, the run ends, a band every few
//                                  floors, each block its own colour (Singapore's HDB repainting schemes)
//   corridorAccess (corridors)     a corridor-access slab's open corridor face: a parapet at every floor, the shaded
//                                  corridor behind it with the flats' doors and windows (HDB slabs, deck-access blocks)
//   voidDeck      (voidDeck)       an open ground floor under a block: columns every two bays, a beam, the shade
//                                  between them (HDB's void decks, pilotis)
//   fiveFootWay   (fiveFootWay)    a shophouse row's arcade: piers at the run's ends and every ~4.2 m, the shaded
//                                  walkway, the shop front at its back (dark, lit or shuttered), a signboard over it
//   shophouseFront (shophouseFront) a shophouse's upper floors: paired louvred timber shutters beside or over tall
//                                  windows (each front its own colour), pilasters at the party walls, sill bands
//   colonnade     (colonnade)      columns at every bay through the floors, a shaded verandah between them (colonial
//                                  civic buildings, a giant order)
//   balconySlabs  (balconySlabs)   white slab edges at every floor (condominium towers with balconies)
const { float, f01, sel, band, stripe, h1, hash2, corniceShadow, palette } = await import(`./core.js${new URL(import.meta.url).search}`);
import { vec3, mix, max, abs, floor, round, clamp, smoothstep, fract } from 'three/tsl';

// ---------------------------------------------------------------- Gründerzeit stucco
// the horizontal profiles, where the floors are resolved (a grazing view along a street): courses (the fronts with
// string courses), light (the stucco's lit colour). Returns the profile's colour, its weight and the cornice's mask
export const gruenderzeitProfile = (V, courses, light) => {
  const course = f01(courses.and(V.row.greaterThan(0.5))).mul(band(V.cy, float(0.0), sel(V.row.equal(1), float(0.07), float(0.045)), V.wy));
  const courseShade = f01(courses.and(V.row.greaterThan(0.5))).mul(band(V.cy, float(0.95), float(1.0), V.wy));
  const under = V.wallH.sub(V.corniceH);
  const corShade = corniceShadow(V, 0.45);
  let hc = mix(mix(V.wall, light, course), V.wall.mul(0.6), courseShade.mul(0.75));
  hc = mix(hc, V.wall.mul(0.5), corShade.mul(0.6));
  const cz = V.y.sub(under).div(max(V.corniceH, 0.1));
  const inCor = V.cornice;
  const czW = V.fyM.div(max(V.corniceH, 0.1));
  const dent = stripe(V.s.div(0.22), float(0), float(0.5), V.fsB.div(0.22));
  const cons = stripe(V.s.div(0.9), float(0), float(0.24), V.fsB.div(0.9));
  const lightC = light.mul(1.04).min(vec3(0.95));
  // (stucco: the full profile; stripped: plain)
  let pc = mix(V.wall.mul(0.86), lightC, cons.mul(0.85));                           // frieze with consoles
  pc = mix(pc, V.wall.mul(0.42), band(cz, float(0.36), float(0.47), czW));            // soffit shadow
  pc = mix(pc, mix(V.wall.mul(0.7), lightC, dent), band(cz, float(0.47), float(0.6), czW));   // dentils
  pc = mix(pc, mix(lightC, V.wall.mul(0.68), band(cz, float(0.84), float(0.9), czW)), band(cz, float(0.6), float(1.05), czW));   // corona, shadow line
  let plain = mix(V.wall.mul(0.97), V.wall.mul(0.5), band(cz, float(0.0), float(0.18), czW));
  plain = mix(plain, light, band(cz, float(0.75), float(1.05), czW));
  const prof = sel(courses, pc, plain);
  return { colour: mix(hc, prof, inCor), weight: max(max(course, courseShade.mul(0.75)), max(corShade.mul(0.6), inCor)), cornice: inCor };
};
// surrounds, hoods and a pediment over the Beletage's windows (a triangle on every other building, a segment on the
// rest) on the stucco fronts (stucco), sills on all (M4 fix round: wider surrounds, a deeper shaded hood. A reveal, an
// aedicule's pilasters and a sill shadow were tried and left out: the shader's size alone cost the overview 15 ms)
export const gruenderzeitSurrounds = (V, stucco, notG, light) => {
  const top = round(V.wallH.div(V.fh)).sub(1);              // (the top floor's row)
  const opX = band(V.cx, V.xlo, V.xhi, V.wx), opY = band(V.cy, V.ylo, V.yhi, V.wy);
  const surX = band(V.cx, V.xlo.sub(0.085), V.xhi.add(0.085), V.wx), surY = band(V.cy, V.ylo.sub(0.06), V.yhi.add(0.045), V.wy);
  const surround = surX.mul(surY).sub(opX.mul(opY)).max(0);
  const bel = f01(V.row.equal(1));
  const pedH = sel(V.row.equal(1), float(0.15), float(0.07));
  const hoodX = band(V.cx, V.xlo.sub(0.12), V.xhi.add(0.12), V.wx);
  const hood = hoodX.mul(band(V.cy, V.yhi.add(0.05), V.yhi.add(0.05).add(pedH), V.wy));
  // the pediment: the hood's top cut to a triangle (or a flat segment) over the Beletage
  const half = V.xhi.sub(V.xlo).mul(0.5).add(0.12);
  const tri = float(1).sub(abs(V.cx.sub(0.5)).div(half)).max(0);
  const triH = sel(h1(V.seed.mul(7.31)).lessThan(0.5), tri.mul(0.13), tri.min(0.3).mul(0.2));
  const pediment = bel.mul(hoodX).mul(band(V.cy, V.yhi.add(0.05).add(pedH), V.yhi.add(0.05).add(pedH).add(triH), V.wy));
  const hoodShade = hoodX.mul(band(V.cy, V.yhi.add(0.042), V.yhi.add(0.065), V.wy));
  const sill = band(V.cx, V.xlo.sub(0.07), V.xhi.add(0.07), V.wx).mul(band(V.cy, V.ylo.sub(0.065), V.ylo.sub(0.01), V.wy));
  const sOn = f01(stucco.and(notG()).and(V.row.lessThan(top.add(0.5))));
  let c = mix(V.wall, light, clamp(surround.add(hood).add(pediment), 0, 1).mul(sOn).mul(0.88));
  c = mix(c, V.wall.mul(0.55), hoodShade.mul(sOn).mul(0.65));
  return mix(c, light, sill.mul(f01(notG())).mul(0.85));
};
// the French balcony's stucco slab with its shaded front edge at the door's foot (mask: V.altBalc)
export const frenchBalcony = (V, c) => {
  const slabX = band(V.cx, V.xlo.sub(0.14), V.xhi.add(0.14), V.wx);
  return mix(c, V.wall.mul(0.9).add(0.02), slabX.mul(band(V.cy, float(-0.01), float(0.035), V.wy)).mul(V.altBalc));
};
// pilasters at the bays' edges where `on` (the styles' every n-th bay test), lit
export const pilasterStrips = (V, c, on, light) => {
  const pil = f01(on.and(V.row.greaterThan(0.5)))
    .mul(band(V.cx, float(-0.1), float(0.09), V.wx).add(band(V.cx, float(0.91), float(1.1), V.wx)).min(1));
  return mix(c, light, pil.mul(0.75));
};
// a frieze under the cornice (mask: its styles), a running motif every 0.9 m
export const frieze = (V, c, mask, light) => {
  const fr = f01(mask).mul(band(V.y, V.wallH.sub(V.corniceH).sub(1.3), V.wallH.sub(V.corniceH).sub(0.25), V.fyM));
  const motif = stripe(V.s.div(0.9), float(0.15), float(0.55), V.fsB.div(0.9));
  return mix(c, mix(V.wall.mul(0.82), light, motif), fr.mul(0.8));
};
// glazed ceramic tiles (0.32 x 0.24 m, each its own shade) over a grid of joints, faded with V.tileRes (mask: its walls)
export const ceramicTiles = (V, c, mask) => {
  const kma = f01(mask).mul(V.tileRes);
  const tileId = hash2(floor(V.s.div(0.32)), floor(V.y.div(0.24)));
  const tileJ = clamp(stripe(V.y.div(0.24), float(0), float(0.08), V.fyM.div(0.24)).add(stripe(V.s.div(0.32), float(0), float(0.06), V.fsB.div(0.32))), 0, 1);
  c = c.mul(float(1).add(tileId.sub(0.5).mul(0.07).mul(kma)));
  return mix(c, V.wall.mul(0.8), tileJ.mul(kma).mul(0.5));
};

// ---------------------------------------------------------------- slabs and panels
// Plattenbau: panel joints at every floor and every two bays, loggia columns (one bay in three or four, on three in
// four) with coloured balcony fronts (red, orange, yellow, blue, green per building), a darker plinth on most
export const plattenbau = (V) => {
  const jointH = band(V.cy, float(-0.01), float(0.012), V.wy).add(band(V.cy, float(0.988), float(1.01), V.wy));
  const jointV = f01(V.col.mod(2).equal(0)).mul(band(V.cx, float(-0.01), float(0.008), V.wx));
  let c = mix(V.wall, V.wall.mul(0.55), clamp(jointH.add(jointV), 0, 1).mul(0.7));
  const logPer = sel(h1(V.seed.mul(13.3)).lessThan(0.5), float(3), float(4));
  const logCol = h1(V.seed.mul(47.1)).lessThan(0.75).and(V.col.add(floor(V.seed.mul(5))).mod(logPer).equal(1)).and(V.row.greaterThan(0.5));
  const ak = h1(V.seed.mul(29.9));
  const accent = sel(ak.lessThan(0.25), vec3(0.42, 0.12, 0.09), sel(ak.lessThan(0.45), vec3(0.6, 0.3, 0.1),
    sel(ak.lessThan(0.6), vec3(0.62, 0.52, 0.18), sel(ak.lessThan(0.75), vec3(0.2, 0.32, 0.45), sel(ak.lessThan(0.88), vec3(0.3, 0.4, 0.26), V.wall.mul(0.85))))));
  const inBay = f01(logCol).mul(band(V.cx, float(0.04), float(0.96), V.wx));
  const front = inBay.mul(band(V.cy, float(0.02), V.ylo, V.wy));
  const recess = inBay.mul(band(V.cy, V.ylo, float(0.96), V.wy));
  c = mix(mix(c, V.wall.mul(0.35), recess.mul(0.85)), accent, front.mul(0.92));
  const plinth = f01(V.row.lessThan(0.5).and(h1(V.seed.mul(5.7)).lessThan(0.6)));
  return mix(c, V.wall.mul(0.62).add(vec3(0.02)), plinth.mul(0.8));
};
// white slab edges at every floor, coloured balcony panels in some bays (the Hansaviertel's slabs)
export const slabEdges = (V) => {
  const slab = f01(V.row.greaterThan(0.5)).mul(band(V.cy, float(-0.01), float(0.07), V.wy));
  const hk = h1(V.seed.mul(17.7));
  const hCol = sel(hk.lessThan(0.35), vec3(0.64, 0.52, 0.12), sel(hk.lessThan(0.6), vec3(0.6, 0.3, 0.1), sel(hk.lessThan(0.8), vec3(0.22, 0.34, 0.5), vec3(0.75, 0.74, 0.7))));
  const hPanel = f01(h1(V.col.add(V.seed.mul(9.1))).lessThan(0.5).and(V.row.greaterThan(0.5)))
    .mul(band(V.cx, V.xlo, V.xhi, V.wx)).mul(band(V.cy, float(0.08), V.ylo, V.wy));
  return mix(mix(V.wall, vec3(0.78, 0.77, 0.74), slab.mul(0.85)), hCol, hPanel.mul(0.9));
};
// ashlar joints (0.75 m courses, three slabs a bay), a recessed top floor on two in five (post-war Neubau stone)
export const stoneJoints = (V) => {
  const top = round(V.wallH.div(V.fh)).sub(1);
  const stoneJ = clamp(stripe(V.y.div(0.75), float(0), float(0.025), V.fyM.div(0.75)).add(stripe(V.cx.mul(3), float(0), float(0.02), V.wx.mul(3))), 0, 1);
  const c = mix(V.wall, V.wall.mul(0.72), stoneJ.mul(V.tileRes).mul(0.5));
  const staffel = f01(V.row.equal(top).and(h1(V.seed.mul(33.1)).lessThan(0.4)));
  return mix(c, V.wall.mul(0.55), staffel.mul(0.7));
};
// precast concrete: the spandrel bands a shade lighter, joints at the bays
export const precastJoints = (V, light) => {
  const spandrel = band(V.cy, V.yhi, float(1.0), V.wy).add(band(V.cy, float(0), V.ylo, V.wy)).min(1);
  const c = mix(V.wall, light(V.wall), spandrel.mul(0.35));
  return mix(c, V.wall.mul(0.6), band(V.cx, float(-0.01), float(0.01), V.wx).mul(0.5));
};
// buttresses at each bay's edge (mask: their styles)
export const buttresses = (V, c, mask) => {
  const b = f01(mask).mul(band(V.cx, float(-0.08), float(0.08), V.wx).add(band(V.cx, float(0.92), float(1.08), V.wx)).min(1));
  return mix(c, V.wall.mul(0.78), b.mul(0.7));
};

// ---------------------------------------------------------------- terraces and warehouses
// a pillared porch at the door, one bay in three (pale, two columns, the dark door and its fanlight between them; the
// stucco terraces'): porchBay, its test. Returns the porch's mask and colour
export const pillaredPorch = (V, porchBay) => {
  const porch = f01(porchBay).mul(band(V.cx, float(0.06), float(0.94), V.wx)).mul(band(V.cy, float(0), float(0.93), V.wy));
  const colm = band(V.cx, float(0.12), float(0.24), V.wx).add(band(V.cx, float(0.76), float(0.88), V.wx));
  const doorP = band(V.cx, float(0.36), float(0.64), V.wx).mul(band(V.cy, float(0.0), float(0.7), V.wy));
  const fan = band(V.cx, float(0.36), float(0.64), V.wx).mul(band(V.cy, float(0.72), float(0.8), V.wy));
  const entab = band(V.cy, float(0.82), float(0.93), V.wy);
  let pc = mix(V.wall.mul(0.6), V.wall.mul(1.06), colm.mul(sel(V.cx.lessThan(0.5), float(1), float(0.82))).max(entab));
  pc = mix(mix(pc, vec3(0.03, 0.03, 0.035), doorP), vec3(0.06, 0.06, 0.06), fan);
  return { mask: porch, colour: pc };
};
// a column of loading doors (dark timber) one bay in three, each with an iron balcony (a platform and a railing of
// bars) at its foot (Shad Thames, Butlers Wharf): doorCol, the column's test. Returns w over-painted and the door's mask
export const loadingDoors = (V, w, doorCol) => {
  const door = f01(doorCol).mul(band(V.cx, float(0.22), float(0.78), V.wx)).mul(band(V.cy, float(0.02), float(0.86), V.wy))
    .mul(float(1).sub(V.cornice));
  w = mix(w, vec3(0.045, 0.04, 0.035).add(vec3(0.03, 0.012, 0).mul(h1(V.seed.mul(3.7)))), door);
  const bars = stripe(V.cx.mul(14), float(0), float(0.22), V.wx.mul(14));
  const railW = f01(doorCol).mul(band(V.cx, float(0.1), float(0.9), V.wx)).mul(band(V.cy, float(0), float(0.05), V.wy)
    .add(band(V.cy, float(0.3), float(0.33), V.wy)).add(band(V.cy, float(0.05), float(0.3), V.wy).mul(bars)).clamp(0, 1))
    .mul(float(1).sub(V.cornice));
  return { w: mix(w, vec3(0.025, 0.025, 0.028), railW), door };
};

// ---------------------------------------------------------------- Japanese walls
// a tiled band facade (V: the bays branch's copies): tile joints (0.227 x 0.06 m, 二丁掛, stretcher bond) faded out
// before they shimmer, the spandrels (under and over the windows) in a second tile tone on half the buildings, a light
// concrete slab edge at every floor and the shadow under it
// (M4 fix round, speed: the bed joints only, by the floor's scale alone; the stretcher bond's head joints, a second
// stripe with a floor and a mod per pixel, read only within a few metres)
export const tiledBands = (V) => {
  const res = float(1).sub(smoothstep(float(0.15), float(0.5), V.fyM.div(0.06)));
  const bed = stripe(V.y.div(0.06), float(0), float(0.12), V.fyM.div(0.06));
  let c = mix(V.wall, V.wall.mul(0.78), bed.mul(res).mul(0.4));
  const tone = h1(V.seed.mul(41.7));
  const second = sel(tone.lessThan(0.25), V.wall.mul(0.82), sel(tone.lessThan(0.5), V.wall.mul(1.1).add(0.02).min(vec3(0.9)), c));
  const spand = band(V.cy, float(0.06), V.ylo, V.wy).add(band(V.cy, V.yhi, float(0.95), V.wy)).min(1);
  c = mix(c, second, spand.mul(0.8));
  const up = f01(V.row.greaterThan(0.5));
  const slab = up.mul(band(V.cy, float(-0.01), float(0.05), V.wy));
  const shade = band(V.cy, float(0.95), float(1.0), V.wy);
  c = mix(c, V.wall.mul(0.62), shade.mul(0.6));
  return mix(c, vec3(0.7, 0.69, 0.66), slab.mul(0.85));
};
// apartment balcony railings: on every floor above the ground a balcony across the whole front: its railing panel
// (frosted glass, a solid panel in the wall colour or a lighter tone, or dark bars over the balcony's shade) to a
// third of the storey, the slab edge at its foot, a partition board (隔て板) every two bays, the shade under the
// balcony above; the sliding doors behind are the window box (from ylo up)
export const balconyRails = (V) => {
  const up = f01(V.row.greaterThan(0.5));
  const k = h1(V.seed.mul(43.3));
  const front = up.mul(band(V.cy, float(0.05), float(0.36), V.wy));
  const bars = stripe(V.s.div(0.11), float(0), float(0.35), V.fsB.div(0.11));
  const frosted = vec3(0.6, 0.64, 0.66).mul(mix(float(0.92), float(1.04), h1(V.seed.mul(5.1))));
  const solid = sel(h1(V.seed.mul(7.7)).lessThan(0.5), V.wall.mul(1.06).add(0.02).min(vec3(0.92)), V.wall.mul(0.86));
  const barC = mix(V.wall.mul(0.28), vec3(0.18, 0.18, 0.19), bars);
  const panel = sel(k.lessThan(0.38), frosted, sel(k.lessThan(0.78), solid, barC));
  let c = mix(V.wall, V.wall.mul(0.55), up.mul(band(V.cy, float(0.9), float(1.0), V.wy)).mul(0.7));   // shade
  c = mix(c, V.wall.mul(0.42), up.mul(band(V.cy, float(0.36), V.ylo, V.wy)).mul(0.6));                // the balcony's depth
  c = mix(c, panel, front);
  c = mix(c, V.wall.mul(1.08).add(0.03).min(vec3(0.94)), up.mul(band(V.cy, float(-0.01), float(0.05), V.wy)));   // slab edge
  const part = up.mul(f01(V.col.mod(2).equal(0))).mul(band(V.cx, float(-0.02), float(0.02), V.wx)).mul(band(V.cy, float(0.05), float(0.9), V.wy));
  return mix(c, vec3(0.78, 0.78, 0.76), part.mul(0.85));
};
// temples and shrines: timber posts at each bay's edges (vermilion or dark), a tie beam under the eaves and over the
// ground floor, plaster panels between the posts (white on the dark buildings, the wall's on the vermilion)
export const timberFrame = (V) => {
  const red = V.wall.x.greaterThan(V.wall.y.mul(3));
  const timber = sel(red, V.wall, vec3(0.16, 0.11, 0.08));
  const plaster = sel(red, V.wall.mul(1.1).min(vec3(0.85)), vec3(0.8, 0.78, 0.72));
  const post = band(V.cx, float(-0.07), float(0.07), V.wx).add(band(V.cx, float(0.93), float(1.07), V.wx)).min(1);
  const beam = band(V.y, V.wallH.sub(1.1), V.wallH.sub(0.5), V.fyM).add(band(V.y, V.fh.sub(0.35), V.fh, V.fyM)).min(1);
  const c = mix(plaster, V.wall.mul(0.85), f01(red));
  return mix(c, timber, clamp(post.add(beam), 0, 1));
};
// low wooden houses: siding boards every 0.2 m (on half: mortar, a faint trowel line every 0.6 m), faded out before
// they shimmer; a small dark eave (霧除け) over the ground floor's openings
export const lapSiding = (V) => {
  const sid = h1(V.seed.mul(19.3)).lessThan(0.5);
  const pitch = sel(sid, float(0.2), float(0.6));
  const res = float(1).sub(smoothstep(float(0.15), float(0.5), V.fyM.div(pitch)));
  const line = stripe(V.y.div(pitch), float(0), sel(sid, float(0.12), float(0.04)), V.fyM.div(pitch));
  const c = mix(V.wall, V.wall.mul(0.7), line.mul(res).mul(sel(sid, float(0.55), float(0.25))));
  const eave = f01(V.row.lessThan(0.5)).mul(band(V.cx, V.xlo.sub(0.08), V.xhi.add(0.08), V.wx)).mul(band(V.cy, V.yhi.add(0.02), V.yhi.add(0.07), V.wy));
  return mix(c, vec3(0.12, 0.12, 0.13), eave.mul(0.9));
};
// vertical signboards (袖看板) stacked at one end of a narrow front (S: the facade's top-level nodes: s, runLen, y,
// row, cy, wy, fs, fyM, fh, wallH, seed, on): a 0.8 m board from 0.3 m in from the end, one box per floor from the
// second (each its own colour: white, yellow, red, blue, green, black, pink) with a column of glyphs in a contrasting
// colour, or (two in five) one tall board for the building. Returns its mask and colour
const SIGN = [[0.26, [0.86, 0.85, 0.8]], [0.42, [0.82, 0.62, 0.08]], [0.57, [0.6, 0.07, 0.06]], [0.68, [0.08, 0.18, 0.48]],
  [0.77, [0.06, 0.38, 0.18]], [0.9, [0.035, 0.035, 0.04]], [1, [0.8, 0.36, 0.45]]];
export const signboardStack = (S) => {
  const atEnd = sel(h1(S.seed.mul(23.7)).lessThan(0.5), S.s, S.runLen.sub(S.s));
  const w = mix(float(0.7), float(1.0), h1(S.seed.mul(31.3)));
  const colX = band(atEnd, float(0.3), w.add(0.3), S.fs);
  const tall = h1(S.seed.mul(37.9)).lessThan(0.4);
  const top = S.wallH.sub(sel(tall, float(0.4), float(0.9)));
  const rowY = sel(tall, band(S.y, S.fh.add(0.3), top, S.fyM), band(S.cy, float(0.07), float(0.93), S.wy).mul(f01(S.y.lessThan(top))));
  const mask = colX.mul(rowY).mul(f01(S.on.and(S.row.greaterThan(0.5))));
  const k = h1(sel(tall, float(0), S.row.mul(7.1)).add(S.seed.mul(91.3)));
  const colour = palette(k, SIGN);
  const light = k.lessThan(0.42).or(k.greaterThan(0.9));
  const ink = sel(light, sel(h1(S.seed.mul(3.3)).lessThan(0.5), vec3(0.6, 0.06, 0.05), vec3(0.04, 0.04, 0.05)), vec3(0.92, 0.9, 0.84));
  // the glyphs: a column of 0.24 m cells down the board's middle, four in five a glyph, faded to their average
  const u = atEnd.sub(0.3).div(w), du = S.fs.div(w);
  const lv = S.y.div(0.24), dv = S.fyM.div(0.24);
  const res = float(1).sub(smoothstep(float(0.2), float(0.6), max(dv, du.mul(4))));
  // (each glyph a block with strokes cut out of it, by its hash: a horizontal slot, a vertical one, or two bars)
  const gk = h1(floor(lv).add(S.seed.mul(57.1))), gu = u.sub(0.24).div(0.52), gv = fract(lv);
  const cut = sel(gk.lessThan(0.3), band(gv, float(0.42), float(0.56), dv),
    sel(gk.lessThan(0.55), band(gu, float(0.38), float(0.62), du.div(0.52)),
      band(gv, float(0.3), float(0.42), dv).add(band(gv, float(0.6), float(0.7), dv)).mul(band(gu, float(0.2), float(1), du.div(0.52)))));
  const cell = band(gv, float(0.12), float(0.88), dv).mul(float(1).sub(cut.min(1))).mul(f01(gk.lessThan(0.85)));
  const glyph = band(u, float(0.24), float(0.76), du).mul(mix(float(0.42), cell, res));
  return { mask, colour: mix(colour, ink, glyph.mul(0.85)) };
};

// ---------------------------------------------------------------- high-rise housing and shophouses (southern China)
// public housing blocks (Hong Kong's Harmony, Trident and Concord blocks): pastel paint with colour accents in one
// colour per block (salmon, teal, orange, blue, green, yellow, lilac, red): a stripe of 1-2 bays at the ends of each
// wall run or every n bays, a crown band over the top two floors, and a grey, darker ground floor (lobby, void deck)
export const estateAccents = (V) => {
  const ak = h1(V.seed.mul(23.7));
  const accent = sel(ak.lessThan(0.16), vec3(0.72, 0.38, 0.3), sel(ak.lessThan(0.3), vec3(0.2, 0.5, 0.5),
    sel(ak.lessThan(0.44), vec3(0.82, 0.5, 0.2), sel(ak.lessThan(0.58), vec3(0.28, 0.42, 0.66), sel(ak.lessThan(0.7), vec3(0.36, 0.58, 0.36),
      sel(ak.lessThan(0.8), vec3(0.85, 0.7, 0.3), sel(ak.lessThan(0.9), vec3(0.52, 0.42, 0.62), vec3(0.66, 0.22, 0.2))))))));
  const top = round(V.wallH.div(V.fh)).sub(1);
  // stripes: the first and last bay of a run (the wings' ends), or every n-th bay (3-5) on some blocks
  const per = floor(mix(float(3), float(5.99), h1(V.seed.mul(5.1))));
  const ends = V.col.lessThan(0.5).or(V.col.greaterThan(V.bays.sub(1.5)));
  const stripeCol = sel(h1(V.seed.mul(9.7)).lessThan(0.55), f01(ends), f01(V.col.add(floor(V.seed.mul(7))).mod(per).equal(0)));
  const crown = f01(V.row.greaterThan(top.sub(1.5)).and(h1(V.seed.mul(3.3)).lessThan(0.7)));
  const inBay = band(V.cx, float(0.02), float(0.98), V.wx);
  // (on a narrow wing's run the end bays are the whole wall: a painted wing, as many blocks have)
  const acc = clamp(stripeCol.mul(inBay).add(crown), 0, 1).mul(f01(V.row.greaterThan(0.5)));
  let c = mix(V.wall, accent, acc.mul(0.75));
  // a slab edge at every floor (a shade darker), the ground floor grey
  c = mix(c, V.wall.mul(0.86), band(V.cy, float(-0.01), float(0.035), V.wy).mul(f01(V.row.greaterThan(0.5))).mul(0.6));
  return mix(c, vec3(0.42, 0.42, 0.41), f01(V.row.lessThan(0.5)).mul(0.65));
};
// projecting bay windows of the tiled private towers: a lit ledge under the window and its shadow below, a lit
// cheek on the left and a shaded one on the right, a soffit over it
export const bayWindows = (V) => {
  const nx = band(V.cx, V.xlo.sub(0.06), V.xhi.add(0.06), V.wx);
  const ledge = nx.mul(band(V.cy, V.ylo.sub(0.07), V.ylo, V.wy));
  const shade = nx.mul(band(V.cy, V.ylo.sub(0.16), V.ylo.sub(0.07), V.wy));
  const ny = band(V.cy, V.ylo.sub(0.07), V.yhi.add(0.05), V.wy);
  const cheekL = band(V.cx, V.xlo.sub(0.06), V.xlo, V.wx).mul(ny), cheekR = band(V.cx, V.xhi, V.xhi.add(0.06), V.wx).mul(ny);
  const soffit = nx.mul(band(V.cy, V.yhi, V.yhi.add(0.05), V.wy));
  const on = f01(V.row.greaterThan(0.5).and(h1(V.seed.mul(41.3)).lessThan(0.8)));
  // (the tiles' joints close up were left out: Hong Kong's street view on WebGL 2 paid for them on every tower)
  let c = V.wall;
  const lit = V.wall.mul(1.1).add(0.03).min(vec3(0.95));
  c = mix(c, lit, clamp(ledge.add(cheekL).add(soffit), 0, 1).mul(on).mul(0.85));
  return mix(c, V.wall.mul(0.5), clamp(shade.add(cheekR.mul(0.6)), 0, 1).mul(on).mul(0.8));
};
// Cantonese shophouses and post-war walk-ups (tong lau) and the composite buildings over their shops: a balcony at every
// floor over the ground one (by the seed: open with a painted parapet, caged in iron bars, or glazed in, flush), the
// slab's edge and its shadow, soot streaks under the slabs and windows, signboards on the first floor of some (red,
// yellow, white, blue, green). notG(): not the ground floor's shops
export const shophouseBalconies = (V, notG) => {
  const k = h1(V.seed.mul(31.9));
  const up = f01(V.row.greaterThan(0.5).and(notG()));
  const slab = band(V.cy, float(-0.01), float(0.05), V.wy).mul(up);
  const parapet = band(V.cy, float(0.05), V.ylo, V.wy).mul(band(V.cx, float(0.03), float(0.97), V.wx)).mul(up);
  const slabShade = band(V.cy, float(0.88), float(1.0), V.wy).mul(f01(V.row.greaterThan(-0.5)));
  // the parapet: a paler or other-coloured paint (open), iron bars over dark (caged), the wall itself (glazed in)
  const pk = h1(V.seed.mul(12.1));
  const paint = sel(pk.lessThan(0.4), V.wall.mul(1.12).add(0.02), sel(pk.lessThan(0.6), vec3(0.62, 0.66, 0.6),
    sel(pk.lessThan(0.8), vec3(0.6, 0.62, 0.66), vec3(0.7, 0.6, 0.52))));
  const bars = stripe(V.s.div(0.12), float(0), float(0.35), V.fsB.div(0.12));
  const cage = mix(vec3(0.06, 0.065, 0.07), vec3(0.32, 0.33, 0.33), bars);
  const parC = sel(k.lessThan(0.5), paint, sel(k.lessThan(0.78), cage, V.wall.mul(0.95)));
  let c = mix(V.wall, parC, parapet.mul(0.92));
  c = mix(c, V.wall.mul(1.08).add(0.04).min(vec3(0.9)), slab.mul(0.8));
  c = mix(c, V.wall.mul(0.45), slabShade.mul(up).mul(0.55));
  // soot: streaks under the slabs and the windows' corners, deeper on some fronts
  const soot = h1(floor(V.s.div(0.6)).add(V.seed.mul(17.3))).mul(band(V.cy, float(0.05), float(0.7), V.wy))
    .mul(mix(float(0.1), float(0.3), h1(V.seed.mul(6.7))));
  c = c.mul(float(1).sub(soot.mul(up)));
  // signboards on the first floor (three in five fronts), a board per one or two bays
  const sk = h1(V.col.add(V.seed.mul(73.1)));
  const board = f01(V.row.equal(1).and(h1(V.seed.mul(2.9)).lessThan(0.6)).and(sk.lessThan(0.7)))
    .mul(band(V.cx, float(0.04), float(0.96), V.wx)).mul(band(V.cy, float(0.12), float(0.9), V.wy));
  const signC = sel(sk.lessThan(0.18), vec3(0.62, 0.06, 0.05), sel(sk.lessThan(0.32), vec3(0.85, 0.66, 0.08),
    sel(sk.lessThan(0.46), vec3(0.85, 0.84, 0.8), sel(sk.lessThan(0.58), vec3(0.08, 0.2, 0.5), vec3(0.06, 0.38, 0.18)))));
  return { colour: mix(c, signC, board), board };
};
// flatted factories: the concrete spandrel bands between the ribbon windows a shade lighter, rain streaks down them,
// roller shutters (grey, ribbed) on the ground floor one bay in two
export const ribbonSpandrels = (V, notG) => {
  const spand = band(V.cy, V.yhi, float(1.01), V.wy).add(band(V.cy, float(-0.01), V.ylo, V.wy)).min(1);
  const streak = h1(floor(V.s.div(0.8)).add(V.seed.mul(11.3))).mul(band(V.cy, float(-0.01), V.ylo, V.wy)).mul(0.22);
  let c = mix(V.wall, V.wall.mul(1.08).add(0.02).min(vec3(0.9)), spand.mul(0.6));
  c = c.mul(float(1).sub(streak));
  const shutter = f01(V.row.lessThan(0.5).and(notG()).and(V.col.mod(2).equal(0)))
    .mul(band(V.cx, float(0.08), float(0.92), V.wx)).mul(band(V.cy, float(0.0), float(0.78), V.wy));
  const ribs = stripe(V.y.div(0.12), float(0), float(0.4), V.fyM.div(0.12));
  return { colour: mix(c, mix(vec3(0.5, 0.51, 0.5), vec3(0.36, 0.37, 0.37), ribs), shutter), shutter };
};
// colonial verandahs (a colonnade or arcade on the lowest two floors): piers at the bays' edges, the dark verandah
// between them under a round arch on the ground floor, a flat lintel on the first; a cornice along the top
export const verandahArcade = (V) => {
  const lowRows = f01(V.row.lessThan(1.5));
  const pier = band(V.cx, float(-0.02), float(0.16), V.wx).add(band(V.cx, float(0.84), float(1.02), V.wx)).min(1);
  const dx = V.cx.sub(0.5).div(0.34);
  const archTop = sel(V.row.lessThan(0.5), float(0.7).add(float(0.2).mul(float(1).sub(dx.mul(dx)).max(0).sqrt())), float(0.86));
  const recess = float(1).sub(pier).mul(smoothstep(archTop.add(V.wy), archTop.sub(V.wy), V.cy)).mul(lowRows);
  let c = mix(V.wall, V.wall.mul(0.3), recess.mul(0.85));
  // a cornice: a lit band along the top with its shadow under it (drawn here, not by the core's masonry cornice: that
  // would build the cornice into every wall pixel of the city for twenty buildings)
  const lit = V.wall.mul(1.08).add(0.03).min(vec3(0.93));
  c = mix(c, lit, band(V.y, V.wallH.sub(1.1), V.wallH.sub(0.3), V.fyM).mul(0.9));
  c = mix(c, V.wall.mul(0.5), band(V.y, V.wallH.sub(1.35), V.wallH.sub(1.1), V.fyM).mul(0.7));
  return { colour: mix(c, lit, pier.mul(lowRows).mul(0.5)), recess };
};

// a windowless wall in square ceramic tiles (0.3 m, each its own shade by its hash) over a grid of paler joints, both
// faded with V.tileRes; a darker plinth (the lowest 1.2 m) and the foot of the wall darkened by rain up to ~4 m
export const tiledWall = (V) => {
  const tileId = hash2(floor(V.s.div(0.3)), floor(V.y.div(0.3)).add(V.seed.mul(61.3)));
  const joints = clamp(stripe(V.y.div(0.3), float(0), float(0.07), V.fyM.div(0.3)).add(stripe(V.s.div(0.3), float(0), float(0.07), V.fsB.div(0.3))), 0, 1);
  let c = V.wall.mul(float(1).add(tileId.sub(0.5).mul(0.12).mul(V.tileRes)));
  c = mix(c, V.wall.mul(1.12).add(0.03).min(vec3(0.92)), joints.mul(V.tileRes).mul(0.55));
  c = c.mul(float(1).sub(float(1).sub(smoothstep(float(0.5), float(4), V.y)).mul(0.18)));
  return mix(c, V.wall.mul(0.55), band(V.y, float(-1), float(1.2), V.fyM));
};

// ---------------------------------------------------------------- tropical blocks and rows (on the wall itself)
// These take the facade's own nodes (c: wall, seed, y, F, X, cx, cy, fx, fy, wy, fyM, fs, s, runLen, wallH, fh, row) and
// a mask node (on), and return the wall painted; every edge box-filtered (stripe), so far away each averages out.
// accent paint: a band over the top floor or two (three blocks in five), the ends of runs over 12 m (half of them), a
// band every 4-6 floors from the first (a third); the colours of HDB's repainting schemes (terracotta, ochre, teal,
// blue, green, maroon, orange, mauve, sand), linear; (Singapore M7, critic: Tiong Bahru's stripes too saturated) each
// 40 % of the way to its own luminance
export const paintBands = (c, on) => {
  const accent = palette(h1(c.seed.mul(23.7)), [[0.14, [0.324, 0.144, 0.108]], [0.26, [0.473, 0.341, 0.191]], [0.38, [0.123, 0.243, 0.249]],
    [0.5, [0.114, 0.168, 0.294]], [0.62, [0.214, 0.31, 0.172]], [0.72, [0.208, 0.07, 0.076]], [0.82, [0.552, 0.282, 0.162]],
    [0.9, [0.263, 0.185, 0.263]], [1, [0.464, 0.404, 0.314]]]);
  const topY = c.wallH.sub(c.fh.mul(sel(h1(c.seed.mul(6.7)).lessThan(0.5), float(1), float(2))));
  const top = f01(h1(c.seed.mul(5.1)).lessThan(0.6)).mul(smoothstep(topY.sub(c.fyM), topY, c.y));
  const endW = clamp(c.runLen.mul(0.12), 2.5, 6);
  const ends = f01(h1(c.seed.mul(8.3)).lessThan(0.5).and(c.runLen.greaterThan(12)))
    .mul(band(c.s, float(-1), endW, c.fs).add(band(c.s, c.runLen.sub(endW), c.runLen.add(1), c.fs)).min(1));
  const every = floor(mix(float(4), float(6.99), h1(c.seed.mul(9.3))));
  const floors = f01(h1(c.seed.mul(12.1)).lessThan(0.35).and(c.F.greaterThan(1)))
    .mul(stripe(c.F.sub(1).div(every), float(0), float(0.3).div(every), c.fy.div(every)));
  return mix(c.wall, accent, clamp(top.add(ends).add(floors), 0, 1).mul(f01(on)).mul(0.9));
};
// a corridor face (on): per floor the parapet (a lit lip at its top), the corridor's shade behind it, the flats' doors
// and gates (dark) and their kitchen windows (grey, grilles), the slab edge over it
export const corridorAccess = (c, on) => {
  const recess = stripe(c.F, float(0.37), float(0.95), c.fy);
  const lip = stripe(c.F, float(0.33), float(0.37), c.fy);
  const door = stripe(c.X, float(0.12), float(0.4), c.fx).mul(stripe(c.F, float(0.4), float(0.92), c.fy));
  const win = stripe(c.X, float(0.56), float(0.86), c.fx).mul(stripe(c.F, float(0.52), float(0.84), c.fy));
  let w = mix(c.wall, c.wall.mul(1.06).min(vec3(0.95)), lip.mul(0.8));
  w = mix(w, c.wall.mul(0.5), recess);
  w = mix(w, vec3(0.09, 0.08, 0.07), door.mul(0.7));
  w = mix(w, vec3(0.13, 0.135, 0.14), win.mul(0.75));
  return mix(c.wall, w, f01(on));
};
// a void deck (on: the ground floor): columns every two bays and at the run's ends, a beam over them, the open floor's
// shade between them, lighter towards the ground (its tiles, the daylight through it)
export const voidDeck = (c, on) => {
  const pillar = stripe(c.X.div(2), float(0), float(0.14), c.fx.div(2));
  const ends = band(c.s, float(-1), float(1.2), c.fs).add(band(c.s, c.runLen.sub(1.2), c.runLen.add(1), c.fs)).min(1);
  const beam = band(c.cy, float(0.86), float(1.05), c.wy);
  const solid = clamp(pillar.add(ends).add(beam), 0, 1);
  const shade = mix(vec3(0.045, 0.045, 0.043), vec3(0.15, 0.15, 0.14), smoothstep(float(0.55), float(0), c.cy));
  return mix(c.wall, mix(shade, c.wall.mul(0.94), solid), f01(on));
};
// a five-foot way (on: the ground floor): the recessed arcade along a shophouse row. Piers at the run's ends (the party
// walls) and about every 4.2 m between (one shop front each), lit on one side; between them the walkway in deep shade
// (darkest under the floor above, a little light off its tiles), the shop front at its back: the doorway (dark, lit
// warm on two in five, a grey roller shutter on one in five) between pale jambs; the kerb of the walkway; over the
// opening the fascia with a signboard on three shops in five (black, green, red, cream, gold)
export const fiveFootWay = (c, on) => {
  const n = max(float(1), round(c.runLen.div(4.2)));
  const unit = c.runLen.div(n);
  const u = c.s.div(unit), fu = c.fs.div(unit), shop = floor(u);
  const pw = float(0.55).div(unit);
  const pier = clamp(stripe(u, float(0), pw, fu).add(band(c.s, c.runLen.sub(0.55), c.runLen.add(1), c.fs)), 0, 1);
  const pierLit = stripe(u, float(0), pw.mul(0.45), fu);
  const opening = band(c.cy, float(-1), float(0.78), c.wy);
  // (Singapore M7, critic: black recesses; the real arcades are bright even in shade, their soffits lit off the street)
  const shade = c.wall.mul(mix(float(0.64), float(0.5), smoothstep(float(0.05), float(0.78), c.cy)));
  const k = h1(shop.add(c.seed.mul(41.3)));
  const inside = sel(k.lessThan(0.4), vec3(0.3, 0.23, 0.13), sel(k.lessThan(0.6), vec3(0.4, 0.4, 0.38), vec3(0.13, 0.12, 0.11)));
  const door = stripe(u, float(0.24), float(0.8), fu).mul(band(c.cy, float(0.035), float(0.6), c.wy));
  const kerb = band(c.cy, float(-1), float(0.035), c.wy);
  const kb = h1(shop.add(c.seed.mul(7.9)));
  const board = f01(kb.lessThan(0.6)).mul(stripe(u, float(0.16), float(0.92), fu)).mul(band(c.cy, float(0.82), float(0.95), c.wy));
  const boardC = palette(h1(shop.add(c.seed.mul(3.1))), [[0.3, [0.03, 0.03, 0.03]], [0.5, [0.03, 0.12, 0.05]], [0.7, [0.35, 0.03, 0.02]],
    [0.85, [0.7, 0.66, 0.55]], [1, [0.5, 0.33, 0.06]]]);
  let back = mix(shade, inside, door.mul(0.92));
  back = mix(back, vec3(0.32, 0.31, 0.29), kerb);
  let w = mix(c.wall, back, opening.mul(float(1).sub(pier)));
  w = mix(w, mix(c.wall.mul(0.82), c.wall.mul(1.04).min(vec3(0.95)), pierLit), pier.mul(opening));
  w = mix(w, boardC, board);
  return mix(c.wall, w, f01(on));
};
// a Straits shophouse's upper floors (on): tall windows (the core's, in the style's window box) between pairs of timber
// louvred shutters, each leaf half the window wide, folded open against the wall either side or closed over the window
// (shophouseClosed: about a third; the core leaves those windows out), every front its own shutter colour (dark green,
// teal, blue, brown, maroon, white, sage); pilasters at the front's ends (the party walls) with their shadow; a moulded
// sill band at each floor
export const shophouseClosed = (c) => h1(c.col.mul(3.7).add(c.row.mul(9.1)).add(c.seed.mul(5.3))).lessThan(0.35);
export const shophouseFront = (c, on, closed) => {
  const leaf = c.xhi.sub(c.xlo).mul(0.5);
  const yb = stripe(c.F, c.ylo, c.yhi, c.fy).mul(c.cut);
  const sides = stripe(c.X, c.xlo.sub(leaf), c.xlo, c.fx).add(stripe(c.X, c.xhi, c.xhi.add(leaf), c.fx));
  const over = stripe(c.X, c.xlo, c.xhi, c.fx);
  const shut = yb.mul(sel(closed, over, sides));
  const sc = palette(h1(c.seed.mul(71.3)), [[0.22, [0.05, 0.15, 0.08]], [0.36, [0.03, 0.17, 0.17]], [0.5, [0.05, 0.1, 0.24]],
    [0.64, [0.15, 0.07, 0.03]], [0.74, [0.24, 0.04, 0.04]], [0.88, [0.74, 0.73, 0.68]], [1, [0.22, 0.33, 0.22]]]);
  const louvre = stripe(c.y.div(0.075), float(0), float(0.5), c.fyM.div(0.075)).mul(0.3).add(0.72);
  const stile = f01(closed).mul(stripe(c.X, float(0.485), float(0.515), c.fx));
  // (Singapore M7, critic: Pagoda Street's white pilasters and sill bands) the pilasters and sills near-white plaster
  const lit = mix(c.wall.mul(1.07).add(0.02), vec3(0.86, 0.85, 0.8), 0.6).min(vec3(0.95));
  const pil = band(c.s, float(-1), float(0.42), c.fs).add(band(c.s, c.runLen.sub(0.42), c.runLen.add(1), c.fs)).min(1);
  const pilShadow = band(c.s, float(0.42), float(0.56), c.fs).add(band(c.s, c.runLen.sub(0.56), c.runLen.sub(0.42), c.fs)).min(1);
  const sill = stripe(c.F, float(0), float(0.06), c.fy);
  let w = mix(c.wall, lit, sill.mul(0.9));
  w = mix(w, c.wall.mul(0.78), pilShadow.mul(0.7));
  w = mix(w, lit, pil);
  w = mix(w, sc.mul(louvre).mul(float(1).sub(stile.mul(0.6))), shut);
  return mix(c.wall, w, f01(on));
};
// columns at every bay's edge (on), lit on one side, their shadow on the verandah's wall beside them, the wall between a
// shade deeper
export const colonnade = (c, on) => {
  const xc = c.X.add(0.08);
  const colM = stripe(xc, float(0), float(0.16), c.fx);
  const lit = stripe(xc, float(0), float(0.08), c.fx);
  const shadow = stripe(xc, float(0.16), float(0.25), c.fx);
  let w = mix(c.wall.mul(0.93), c.wall.mul(0.74), shadow);
  w = mix(w, c.wall.mul(0.97), colM);
  w = mix(w, c.wall.mul(1.06).min(vec3(0.95)), lit);
  return mix(c.wall, w, f01(on));
};
// white slab edges at every floor from the first (on)
export const balconySlabs = (c, on) => {
  const slab = stripe(c.F, float(0), float(0.07), c.fy).mul(f01(c.row.greaterThan(0.5)));
  return mix(c.wall, vec3(0.78, 0.78, 0.75), slab.mul(f01(on)).mul(0.85));
};
