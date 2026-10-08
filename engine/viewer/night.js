// Dusk and night: the twilight and night sky (TSL, composited over the SkyMesh), the light of the scene
// after sunset (hemisphere, moon, haze, exposure) and the schedule of the city's own lights: which share of
// the offices, homes, urban-village rooms, shops, factories and public buildings are lit at a given hour.
// The facades (facade.js), streets (ground.js) and cars (cars.js) read the shared uniforms made here. Their
// lights live in a lit copy of each material (withLights), which the scene's meshes are switched to while
// the lights are on (the sun below 6 degrees) and back from by day: daylight draws exactly the shaders it
// always did (even a branch skipped by day, on a uniform, cost the facades a tenth of their time).
//
// The sky model is a simple, hand-tuned one (not physical): the Preetham SkyMesh goes dark within a
// degree or two of sunset, so from sunset on a blue-hour sky is added to it: a deep blue zenith, a pale
// horizon, an orange glow over the set sun that narrows and reddens as it sinks, the pink "belt of Venus"
// opposite, all fading with the sun's depth below the horizon (exposed as a photographer would, not as
// the eye adapts); and at any hour with the lights on the city's sky glow, warm and brightest on the haze
// just above the horizon. The same colours give the haze (fog) and the hemisphere light, so land and sky
// meet without a seam; after dark the haze the city lights hangs thickest over it, low down (hazeDepth).
import * as THREE from 'three/webgpu';
import { float, vec2, vec3, vec4, uniform, positionWorld, cameraPosition, normalize, max, min, exp, abs, dot, mix, pow, sqrt, select, smoothstep,
  length, clamp, floor, fract, fwidth, hash } from 'three/tsl';

// The shape of one landmark glow (night.glows) at this pixel, 0..1: inside its circle and height band, times the
// optional terms below. Shared by the facades (facade.js) and the lattice's glazing and fabric (lattice.js: a glow
// with on: 'lattice'). normal: the surface's world normal (for grid). diffuse: its albedo (for pale).
// radial: the brightness at the circle's rim as a share of the centre's ((d / r)^2 between: a tent lit from its
// mast, strongest at the centre and the cone's tip); fade: the brightness at y1 as a share of y0's (a church's
// glass-block walls a little dimmer upwards, a dome lit from its floor); grid: [cell, mullion, vary]: glass blocks
// of `cell` metres in concrete mullions of that share of a cell (unlit), each block's brightness varied by
// ±vary/2, box-filtered to their mean once a cell is under ~2 pixels (Eiermann's walls; Berlin M8 fix round)
export function glowMask(g, normal = null, diffuse = null, pos = positionWorld) {
  const gy = pos.y, [y0, y1] = g.y;
  const d = length(pos.xz.sub(vec2(g.at[0], g.at[1])));
  const f01 = (c) => select(c, float(1), float(0));
  let mask = f01(d.lessThan(g.r)).mul(smoothstep(float(y0 - 0.3), float(y0 + 0.3), gy)).mul(float(1).sub(smoothstep(float(y1 - 0.3), float(y1 + 0.3), gy)));
  const t = clamp(gy.sub(y0).div(y1 - y0), 0, 1);
  if (g.ramp) mask = mask.mul(pow(t, g.ramp));
  if (g.fade != null) mask = mask.mul(mix(float(1), float(g.fade), t));
  if (g.radial != null) { const q = d.div(g.r); mask = mask.mul(mix(float(1), float(g.radial), q.mul(q))); }
  if (g.pale && diffuse) mask = mask.mul(smoothstep(float(g.pale), float(g.pale + 0.2), dot(diffuse, vec3(0.2126, 0.7152, 0.0722))));
  // (lattice: [cell, width, gap], Tokyo M8 fix round 1: a lattice tower's members lit as lines and the gaps between them
  // darker, gap the gaps' share: diagonal members both ways and a horizontal ring every cell (m) up the wall, width a
  // share of the cell, box-filtered to their mean far off; the Skytree's Iki had been one flat opaque wash)
  if (g.lattice && normal) {
    const [cell, width, gap] = g.lattice;
    const n2 = normal.xz;
    const tan = vec2(n2.y.negate(), n2.x).div(max(length(n2), 1e-3));
    const q = vec2(dot(positionWorld.xz, tan), gy).div(cell);
    const W = float(width);
    const bar = (s) => {
      const fw = max(fwidth(s).mul(1.25), 1e-4);
      const cum = (y) => floor(y).mul(W).add(min(fract(y), W));
      const y = s.add(W.mul(0.5));
      return clamp(cum(y.add(fw.mul(0.5))).sub(cum(y.sub(fw.mul(0.5)))).div(fw), 0, 1);
    };
    const open = float(1).sub(bar(q.x.add(q.y))).mul(float(1).sub(bar(q.x.sub(q.y)))).mul(float(1).sub(bar(q.y).mul(0.8)));
    mask = mask.mul(mix(float(1), float(gap), open));
  }
  if (g.grid && normal) {
    const [cell, mull, vary] = g.grid;
    // (along the wall: the horizontal tangent of its normal; up: the height)
    const n2 = normal.xz;
    const tan = vec2(n2.y.negate(), n2.x).div(max(length(n2), 1e-3));
    const q = vec2(dot(pos.xz, tan), gy).div(cell);
    const fw = max(max(fwidth(q.x), fwidth(q.y)), 1e-4);
    const edge = (x) => smoothstep(float(mull * 0.5), float(mull * 0.5).add(fw), abs(fract(x).sub(0.5)).mul(-1).add(0.5));
    const id = floor(q);
    const v = hash(id.x.add(id.y.mul(331)).add(Math.round(g.at[0])));
    const cellK = edge(q.x).mul(edge(q.y)).mul(mix(float(1 - (vary ?? 0) / 2), float(1 + (vary ?? 0) / 2), v));
    // (their mean when small: a cell's open share times the mean brightness)
    mask = mask.mul(mix(cellK, float((1 - mull) * (1 - mull)), smoothstep(float(0.25), float(0.6), fw)));
  }
  return mask;
}

const smooth = THREE.MathUtils.smoothstep;
// smoothstep from a down to b (a > b): 0 above a, 1 below b
const falling = (x, a, b) => 1 - smooth(x, b, a);

// Share of rooms lit per kind of building, by the hour (local solar time; linear between the keys, wrapping
// at midnight); a city's city.json (night.schedule) replaces any kind's curve. These are Shenzhen's: offices
// empty through the evening but many stay lit late (overtime is common there);
// homes are most lit around 20-22 h; urban villages, dense and busy, stay lit latest; shops (ground floors,
// village streets) close around 22-23 h, malls at 22 h; feature lighting (landmark crowns, lit fins) runs
// from dusk to 23 h. Daytime values hardly matter: the lights are drawn only once the sun is low.
const SHARE = {
  office: [[0, 0.1], [5, 0.05], [7, 0.25], [9, 0.8], [17, 0.8], [18, 0.66], [19, 0.52], [20, 0.42], [21, 0.34], [22, 0.26], [23, 0.17], [24, 0.1]],
  home: [[0, 0.2], [1, 0.11], [3, 0.05], [5, 0.06], [6, 0.17], [7, 0.27], [8, 0.17], [17, 0.21], [18, 0.34], [19, 0.44], [20, 0.49], [21, 0.5], [22, 0.46], [23, 0.35], [24, 0.2]],
  village: [[0, 0.32], [2, 0.13], [4, 0.07], [6, 0.19], [8, 0.22], [17, 0.26], [18, 0.4], [19, 0.5], [21, 0.56], [22, 0.54], [23, 0.45], [24, 0.32]],
  shops: [[0, 0.32], [2, 0.12], [5, 0.1], [7, 0.45], [9, 0.8], [21, 0.86], [22, 0.72], [23, 0.52], [24, 0.32]],
  mall: [[0, 0.08], [8, 0.3], [10, 0.8], [21, 0.8], [22, 0.5], [23, 0.2], [24, 0.08]],
  factory: [[0, 0.26], [6, 0.26], [8, 0.6], [18, 0.56], [20, 0.4], [22, 0.3], [24, 0.26]],
  civic: [[0, 0.08], [7, 0.3], [9, 0.7], [17, 0.6], [18, 0.42], [20, 0.26], [22, 0.12], [24, 0.08]],
  feature: [[0, 0], [16.5, 0], [17, 1], [22.8, 1], [23.2, 0], [24, 0]],
};
const share = (keys, h) => {
  h = ((h % 24) + 24) % 24;
  for (let i = 1; i < keys.length; i++) {
    const [h1, v1] = keys[i];
    if (h <= h1) { const [h0, v0] = keys[i - 1]; return v0 + (v1 - v0) * (h - h0) / Math.max(h1 - h0, 1e-6); }
  }
  return keys[keys.length - 1][1];
};

// where the moon hangs at night (compass azimuth, elevation): high in the south-east, a dim cool light (a
// city south of the equator has it in the north-east: city.json's night.moon)
const MOON = { azimuth: 140, elevation: 48 };
// the haze lit from below by the city (hazeDepth): its density thins with height over GLOW_H metres; at
// ground level it adds GLOW_TAU of optical depth per metre (about a twelfth over a kilometre)
const GLOW_H = 100, GLOW_TAU = 0.8e-4;

// schedule: kinds of building whose SHARE curve the city replaces; moon: its { azimuth, elevation }
// flood: the floodlit monuments' light ({ tint: [r, g, b], gain, min }: its colour on their stone, a strength
// factor, the least strength whatever the landmark's variant; the defaults are New York's white wash);
// goldTower: the colour and strength (linear) of a lattice tower lit from inside (the Eiffel Tower's sodium gold:
// its lattice, lattice.js, and its solid members, the floodlit style's parts over 300 m), [0, 0, 0] none;
// sparkle: { from, to } hours: the first 5 minutes of each hour between them the lattice twinkles white (the
// Eiffel Tower's 20,000 flash bulbs), null none; dusk: { warm } tints the twilight's afterglow and horizon (0: as
// tuned for Shenzhen; 1: a clear evening's orange-gold horizon under a deep blue); goldLevels, goldBase: the heights
// (m over goldBase, the tower's foot in scene y) of the lattice tower's lamp stages, [] a plain upward ramp
// (flood also takes: spires, the strength of the light on spire-style parts under 300 m (domes, lead spires and
// crowns of floodlit monuments: Paris's Opéra dome, Notre-Dame's flèche), 0 none (New York's steel masts stay
// dark); roofTint, their light's colour (cooler: a green copper dome keeps its green); at: [[x, z, radius], ...]
// circles (scene metres) inside which any building is floodlit as a monument, its windows dark (a landmark
// drawn in an ordinary style: the Tour Saint-Jacques, Notre-Dame's towers)); bridges: the strength of the wash
// on bridges' walls, piers and pylons (gilt, saturated gold-coloured parts glow brighter), 0 none
// (and, Berlin M8 fix round: fallM, the light's fall with height over that many metres from the part's foot (bright
// plinth, about half at a 20 m cornice) instead of over the part's own height; roof, the strength on upward faces
// (default 0.45: unlit roofs want ~0.05); low, parts lower than that (m) get none: a mural wall keeps the night's light;
// ground, the scene height fallM is measured from (a flat city's street level) instead of each part's foot)
// dimDusk: [share at sunset, sun elevation at which the lights reach full strength]: the city's lights come on
// over twilight instead of at full strength from the first (null: as before)
// glows: [{ at: [x, z], r, y: [y0, y1], colour: [r, g, b], k, ramp, pale }]: feature lighting of a landmark (facade.js):
// every building surface inside the circle (scene metres) between scene heights y0 and y1 glows in that colour (linear)
// times k, times ((y - y0) / (y1 - y0))^ramp with a ramp (brightest at the top: a lit spire), and with pale (an albedo
// luminance) only surfaces paler than that (a clock's opal dials, not the stone round them); per pixel, a few at most.
// The Elizabeth Tower's dials, the London Eye's rim, the Shard's spire. [] none
// (Berlin M8 fix round, all optional, see glowMask: on: 'lattice' lights the lattice material's glazing and fabric inside
// the circle instead of the buildings (a membrane roof, a glass dome lit from within), members: its cables' share of the
// light (default 0.35); radial, fade, grid; dark: the buildings' own lights (windows, floodlight) off inside the glow)
// roofLamps: the strength of the odd lamp over a roof door (facade.js), 0 none (each a pool of light on a roof)
// busLights: buses' saloons lit at night, their glass glowing warm white at that strength (cars.js), 0 none
// carSpots: far cars' boxes show their lamps as two spots on each end once a few pixels wide (cars.js), not lit ends
// sky: { zenith: [r, g, b], glowTop, glowFall } (null: as before): the night zenith's own colour at full lights (linear;
// default [0.002, 0.003, 0.0065]), the share of the sky glow still seen overhead (default 0.06: with a warm glow the
// zenith went maroon-brown, Paris M8) and how fast the glow thins with height above the horizon (default 10)
// ambient: { k, tint, ground, fog, fogTint } (null: as before): after dark the hemisphere light's night share times k, its sky
// colour times tint, its ground colour (the city's warm light from below), and the night haze's colour times fog and fogTint (London M8 fix round: the warm haze and fill
// tinted every far roof amber; real aerial night photos show near-black roofs under a warm glow only at the horizon)
// duskFill: { k, colour } (null: none): a cool fill from the blue sky while twilight lasts (k at the full twilight,
// fading with it): dusk is lighter below the horizon than night, not night under a lighter sky
// lampDusk: the street lamps' strength over twilight as dimDusk's first value is the windows' (null: the same):
// lamps come on at full power, windows fill up through the evening (u.lampLights)
// windows: { zone, litFloor, darkFloor, even, vary, office, max, cool, neutral } (facade.js; null: as before): offices' zone width
// in bays, the share of rooms lit on a lit and on a dark floor, even (1: no blind variation inside lit panes), the lit
// rooms' cap (linear), and the offices' cool and neutral lamp colours; vary, each zone of an even floor ±vary/2 (a lit floor not one light box); office, the
// offices' lit rooms times that (Berlin M8 fix round: 0.55, the lit floors outshone the landmarks)
// homeStyles: facade styles lit as homes at night (facade.js; [] none: only 'residential')
// goldLattice (null: as before; Paris, 7 Oct): the lattice tower lit from inside after dark, its members glowing and the gaps
// between them open (lattice.js, and the solid members in facade.js), all optional: at [x, z] (scene m: the tower's axis;
// a panel seen from the side that faces it shows its lit inner face, inside, from the other its outer one, outside);
// veil, the share of the members' fine lacing kept after dark (the brown veil that fills the gaps by day: open gaps,
// the city and the sky through them); lace, the lacing's glow beside the main members'; fall, pool, floor: each lamp
// stage's light over its height, pool x exp(-(m above the stage) / fall) + floor; under, underM: the decks' undersides
// and friezes lit from below, under x exp(-(m below the next stage) / underM); top: [from, to, k], the light falling
// to k between those heights (m over goldBase: the upper shaft dimmer); solid: the solid members' gold times that;
// gain: all of it; pale: [from, to, [r, g, b]], the gold's colour turning towards that one between those heights (Tokyo).
// The numbers are uniforms (__viewer.night.u.goldLattice) for tuning from the console
// corridors: { k, colour, cool, coolShare, dead, every } (null: none; Singapore M8): a corridor-access slab's open corridor
// faces (the styles' `corridors` pattern, facade/patterns.js) lit after dark, all night: per floor the corridor's ceiling
// lamps (one every `every` bays, `dead` of them out) light the corridor behind the parapet, brightest under the ceiling,
// box-filtered to their mean far off (a band per floor, then an even glow); each block's lamps warm `colour` or `cool` (a
// `coolShare` of the blocks); k their brightness (linear, as night.windows' rooms 0.9): HDB estates' rows of lit corridors
// arcades: { k, unit } (null: none; Singapore M8): a shophouse row's five-foot way (the styles' `fiveFootWay` pattern) after
// dark: per shop (unit m, as the pattern's) the shop front and the walkway's soffit lit warm or neutral by the shops' hour,
// their mean far off (the five-foot way's piers and dark shop fronts had left the rows black at night)
// masses: { k, white, patch, dusk } the town ring's windows (masses.js; null: as before); dusk: its walls darken with the
// night's depth (cityGlow), not from the first twilight (Berlin M8 fix round: a 2.4x step along the boundary at dusk)
// homes: { far, room, curtains } (null: as before; Singapore M8 fix round 1) homes' windows after dark (facade.js): far,
// [from, to] in bays a pixel (as facade.farFade) where the lit windows give way to their cell's mean, instead of the
// facade's own grid fade (Singapore's, from ~25 px a bay, had filled every cell with its lit mean: a mosaic of tiles with
// no wall between); room, [lo, hi]: a lit room's brightness, even between them (default 0.22..1.5 on the square:
// many dim rooms, mid-tone tiles); curtains, the share of rooms with curtains drawn (default 0.3: dim brown tiles)
export function createNight({ schedule = {}, moon = MOON, skyGlow = [0.047, 0.04, 0.036], flood = {}, goldTower = [0, 0, 0],
  sparkle = null, dusk = {}, dimDusk = null, goldLevels = [], goldBase = 0, sky = null, glows = [], glowBranch = false, carSpots = false, busLights = 0, roofLamps = 1,
  ambient = null, duskFill = null, lampDusk = null, windows = null, masses = null, homeStyles = [], goldLattice = null,
  corridors = null, arcades = null, homes = null, boards = null, duskGrade = {} } = {}) {
  // duskGrade (8 Oct, the user: "a blue coat at dusk", every city, Hong Kong and Tokyo the most): the blue hour's sky light
  // on the city, dimmer and less blue than before. The old twilight fill (duskFill, the warm dusk's blue hemisphere)
  // lit walls, roofs and streets with a deep-blue sky light about as strong, after the night's exposure, as the day's
  // shade: one flat blue-slate veil, the windows and lamps no match for it. Real blue-hour photos: the sky deep blue,
  // the buildings it alone lights dim and only slightly cool, the street and window light warm and showing. All
  // optional; false (or ?duskfix=0): as before. Applied only while the sun is between 18 degrees below the horizon and
  // the day (window: 1 above -12 deg, 0 under -18), so day and night frames are unchanged:
  //   fill: the twilight fill's (duskFill) strength times this (0.4); twilight: the twilight sky light's (0.7);
  //   colour: the sky light's colour over twilight (linear; [0.55, 0.6, 0.7], B/R 1.27, was up to [0.45, 0.58, 1]);
  //   tint: its share (0.85)
  // and, opt-in (unset: as before; London, 8 Oct, "still cool"): whole, the whole sky light takes the colour (not only the
  // twilight's share: a city's blue night tint, ambient.tint, kept the blue hour navy); zenith, the twilight zenith's
  // brightness times this; moon, the moonlight's share kept; afterglow {k, el, colour}, the western sky's light (see update)
  const gradeOf = (dg) => (dg === false ? null : { fill: 0.4, twilight: 0.7, colour: [0.55, 0.6, 0.7], tint: 0.85, ...dg });
  let GRADE = gradeOf(duskGrade);
  const SKY = { zenith: [0.002, 0.003, 0.0065], glowTop: 0.06, glowFall: 10, ...(sky ?? {}) };
  const FLOOD = { tint: [0.95, 1, 1.05], gain: 1, min: 0, spires: 0, bridges: 0, roofTint: [0.8, 0.95, 1.05], at: [], ...flood };
  const WARM = dusk.warm ?? 0;
  // (dusk, Berlin M8 fix round, all optional: zenith, the blue hour zenith's brightness factor; horizonPow, how high the
  // horizon's colour reaches (0.5; higher: a bluer sky above the lowest few degrees); beltAt, beltFall, belt: the pink
  // belt's height (sin of elevation, 0.1), its fall-off (12) and strength factor; fogGlow: the share of the sun's glow
  // and the belt in the haze over the land (1; the dusk haze read mauve))
  const DUSK = dusk;
  const shares = { ...SHARE, ...schedule };
  const u = {
    // how much the city's lights show: 0 in daylight (sun above 6 degrees), 1 from 4 degrees below the horizon
    lights: uniform(0),
    // the street lamps' strength (lights, or with lampDusk their own share over twilight)
    lampLights: uniform(0),
    // lit shares per kind of building (see SHARE)
    ...Object.fromEntries(Object.keys(shares).map((k) => [k, uniform(0)])),
    // sky colours (linear HDR), set by update()
    zenith: uniform(new THREE.Color(0, 0, 0)), horizon: uniform(new THREE.Color(0, 0, 0)),
    sunGlow: uniform(new THREE.Color(0, 0, 0)), antiGlow: uniform(new THREE.Color(0, 0, 0)),
    skyGlow: uniform(new THREE.Color(0, 0, 0)),
    // how thick the haze lit by the city is (the menu's haze slider)
    hazeK: uniform(1),
    // how much of the sky's light is the city's glow on the haze: none while twilight lasts (from 2 degrees
    // below the horizon), all of it from 9 degrees below
    cityGlow: uniform(0),
    glowHeight: uniform(0.15), sunAz: uniform(new THREE.Vector2(0, 1)),
    // floodlit monuments (facade.js) and a lattice tower's gold (lattice.js, facade.js); sparkle 0/1 by the hour
    floodTint: uniform(new THREE.Color().setRGB(...FLOOD.tint)), floodGain: uniform(FLOOD.gain), floodMin: uniform(FLOOD.min),
    floodSpires: uniform(FLOOD.spires), floodFallM: FLOOD.fallM ?? 0, floodRoof: FLOOD.roof ?? 0.45, floodLow: FLOOD.low ?? 0, floodGround: FLOOD.ground ?? null, floodBridges: uniform(FLOOD.bridges), floodRoofTint: uniform(new THREE.Color().setRGB(...FLOOD.roofTint)), floodAt: FLOOD.at, glows, carSpots, busLights, roofLamps,
    // the lights' strength over twilight (dimDusk): 1 once dark; windows, lamps and floodlights scale with it
    dusk: uniform(1),
    goldTower: uniform(new THREE.Color().setRGB(...goldTower)), sparkle: uniform(0),
    // (the lattice tower's lamps: the heights of its stages over its foot, and the foot's scene height; lattice.js)
    goldLevels, goldBase, windows, masses, homeStyles,
    // (Singapore M8: the corridor faces' lights, facade.js; null none)
    corridors: corridors ? { k: 0.5, colour: [1, 0.86, 0.66], cool: [0.82, 0.9, 1], coolShare: 0.35, dead: 0.04, every: 2, ...corridors } : null,
    arcades: arcades ? { k: 1, unit: 4.2, ...arcades } : null,
    // (Singapore M8 fix round 1: homes' windows, facade.js; null as before)
    homes,
    // (Singapore M9: each building glow computed only where the pixel lies in its circle and height band, facade.js; off:
    // every glow on every building pixel, as before)
    glowBranch,
    // (Hong Kong M8 fix round 1: towers' rooftop sign boards, facade.js; null none)
    boards,
  };
  // (goldLattice: see above; stage(y), the lamps' light at scene height y, the lattice's and the solid members' alike)
  if (goldLattice) {
    const G = { veil: 0.2, lace: 0.5, fall: 40, pool: 0.75, floor: 0.45, under: 0, underM: 6, top: [120, 280, 1], solid: 1,
      inside: 1, outside: 1, gain: 1, ...goldLattice };
    const g = { at: G.at ?? null };
    for (const k of ['veil', 'lace', 'fall', 'pool', 'floor', 'under', 'underM', 'solid', 'inside', 'outside', 'gain']) g[k] = uniform(G[k]);
    g.top = uniform(new THREE.Vector3(...G.top));
    // (pale: [from, to, [r, g, b]] (m over goldBase; linear), default none (Tokyo M8 fix round 1): the gold's colour shifts
    // between those heights from goldTower towards that paler one (Tokyo Tower's Landmark Light: amber on the legs, a pale
    // gold toward the top); colour(y): the gold at scene height y)
    if (G.pale) {
      g.pale = uniform(new THREE.Color().setRGB(...G.pale[2]));
      g.colour = (y) => mix(u.goldTower, g.pale, smoothstep(float(G.pale[0]), float(G.pale[1]), y.sub(goldBase)));
    } else g.colour = null;
    g.stage = (y) => {
      const dy = y.sub(goldBase);
      let above = dy, below = float(1e4);
      for (const L of goldLevels) above = select(dy.greaterThan(L), dy.sub(L), above);
      for (const L of [...goldLevels].reverse()) below = select(dy.lessThan(L), float(L).sub(dy), below);
      const pool = exp(max(above, 0).div(g.fall.negate())).mul(g.pool).add(g.floor);
      const under = exp(below.div(g.underM.negate())).mul(g.under);
      return pool.add(under).mul(mix(float(1), g.top.z, smoothstep(g.top.x, g.top.y, dy))).mul(g.gain);
    };
    u.goldLattice = g;
  } else u.goldLattice = null;
  // Lit copies of materials: withLights(mat, emission) makes a copy of mat (same nodes, same userData) that
  // adds the emission (a vec3 node, scaled by `lights` here) to its own, and returns mat. apply(root) puts
  // the copies on (or takes them off) every mesh below root as the lights are on (or off). The sky has one
  // too (extendSky).
  const litOf = new Map(), dayOf = new Map();
  const COPY = ['name', 'side', 'transparent', 'depthWrite', 'depthTest', 'fog', 'vertexColors', 'roughness', 'metalness',
    'alphaTest', 'alphaToCoverage', 'colorNode', 'roughnessNode', 'metalnessNode', 'normalNode', 'specularColorNode',
    'emissiveNode', 'positionNode', 'vertexNode', 'opacityNode', 'maskNode', 'outputNode', 'receivedShadowPositionNode'];
  const litCopy = (mat) => {
    const lit = new mat.constructor();
    for (const k of COPY) if (k in mat) lit[k] = mat[k];
    if (mat.color) lit.color.copy(mat.color);
    lit.userData = mat.userData;
    litOf.set(mat, lit);
    dayOf.set(lit, mat);
    return lit;
  };
  u.withLights = (mat, emission) => {
    litCopy(mat).emissiveNode = (mat.emissiveNode ?? vec3(0, 0, 0)).add(emission.mul(u.lights));
    return mat;
  };
  // withNight(mat, edit): a lit copy of mat that edit(copy) changes as it likes (the sea's own haze)
  u.withNight = (mat, edit) => {
    edit(litCopy(mat));
    return mat;
  };
  // The haze over the city at night, lit from below by its streets and windows (the night's haze colour,
  // update()): thickest low down and thinning with height (exponentially, over GLOW_H), so it hangs over
  // the city, gathers towards the horizon and is thin where the view looks steeply down from high up. Its
  // optical depth along the sight line from the camera to the point shaded, integrated in closed form (the
  // mean of exp(-h / GLOW_H) between the two heights times the distance), which the night's fog (main.js)
  // and the sea's (water.js) add to the day's haze. dist: the distance along the sight line (the fog's
  // view depth will do). It is left out over the first kilometre or so: close up it only greyed the blacks,
  // and the glow is something seen over the city in the distance.
  // (the camera's height and its term, per render: whichever camera draws, the view's, the glass's probe or
  // the water's mirror, whose camera stands as far below the sea as the view's is above it: its height
  // above the plane is taken, the haze of the path up from the water to what it mirrors, or the whole
  // mirrored city drowned in it. And the strength, faded in with the lights: by day the haze is the day's)
  const camH = uniform(0).onRenderUpdate(({ camera }) => Math.abs(camera.position.y));
  const glowCam = uniform(1).onRenderUpdate(({ camera }) => Math.exp(-Math.abs(camera.position.y) / GLOW_H));
  const glowK = uniform(0).onRenderUpdate(() => GLOW_TAU * u.hazeK.value * u.lights.value);
  u.hazeDepth = (dist) => {
    // mean of exp(-h / H) from the camera's height hc to the point's hp: (exp(-hc / H) - exp(-hp / H)) / x,
    // x = (hp - hc) / H; exp(-hp / H) itself where the two are about level
    const x = positionWorld.y.sub(camH).div(GLOW_H);
    const ep = exp(positionWorld.y.div(-GLOW_H));
    // (branchless: a select between computed nodes can leave one side uninitialised, see facade.js)
    const f01 = (c) => select(c, float(1), float(0));
    const xs = mix(max(x, 1e-3), min(x, -1e-3), f01(x.lessThan(0)));
    const mean = mix(glowCam.sub(ep).div(xs), ep, f01(abs(x).lessThan(1e-3)));
    return mean.mul(dist).mul(glowK).mul(smoothstep(float(800), float(4000), dist));
  };
  const state = { lights: 0, moon: false, on: false };
  // (on: force the copies on or off regardless, for main.js's warm-up)
  function apply(root, on = state.on) {
    const swap = on ? litOf : dayOf;
    root.traverse((o) => { if (o.material && swap.has(o.material)) o.material = swap.get(o.material); });
  }
  const moonDir = new THREE.Vector3(), moonDirGraded = new THREE.Vector3();
  {
    const az = THREE.MathUtils.degToRad(moon.azimuth), el = THREE.MathUtils.degToRad(moon.elevation);
    moonDir.set(Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el));
  }
  const c = new THREE.Color();

  // the sky of dusk and night, added over a SkyMesh's own colour (both the visible sky and the one the
  // environment map is made from), in the sky material's lit copy: by day the sky is drawn as it was
  function extendSky(sky) {
    const day = sky.material.colorNode;
    const dir = normalize(positionWorld.sub(cameraPosition));
    const h = max(dir.y, 0);
    // horizontal direction, compared with the sun's: 1 towards the sun, -1 away
    const flat = vec2(dir.x, dir.z);
    const cosAz = dot(flat.div(max(sqrt(dot(flat, flat)), 1e-4)), u.sunAz);
    let base = mix(u.horizon, u.zenith, pow(h, DUSK.horizonPow ?? 0.5));
    // (a warm dusk: the low sky brighter towards the set sun and darker away from it, not one flat band)
    if (WARM) base = base.mul(mix(float(1 - 0.45 * WARM), float(1 + 0.35 * WARM), cosAz.add(1).mul(0.5).mul(exp(h.mul(-4)))).add(exp(h.mul(-4)).oneMinus()));
    const glow = u.sunGlow.mul(exp(cosAz.sub(1).mul(2.2))).mul(exp(h.negate().div(u.glowHeight)));
    // the belt of Venus: a pink band a few degrees up, opposite the sun
    const belt = u.antiGlow.mul(exp(cosAz.add(1).mul(-1.3))).mul(exp(abs(h.sub(DUSK.beltAt ?? 0.1)).mul(-(DUSK.beltFall ?? 12))));
    // light pollution: the haze over the city lit from below, strongest just above the horizon
    const pollution = u.skyGlow.mul(exp(h.mul(-SKY.glowFall)).add(SKY.glowTop));
    litCopy(sky.material).colorNode = vec4(day.rgb.add(base).add(glow).add(belt).add(pollution), float(1));
  }

  // hour: local solar time; azimuth, elevation: the sun's, in degrees. Sets the uniforms and returns the
  // scene light for main.js: the moon (or null while the sun still lights the scene), hemisphere colours
  // and strength, the haze colour at night and how much it replaces the day's, the exposure, and whether
  // the lit copies have to be switched on or off (`changed`: main.js then calls apply)
  function update(hour, azimuth, elevation) {
    const el = elevation;
    const lights = falling(el, 6, -4);
    state.lights = lights;
    // (dimDusk: over twilight the lights come on at a share of their strength: lamps, windows and floodlights
    // are no match for the sky yet; state.lights, the switch, is not scaled)
    u.dusk.value = dimDusk ? dimDusk[0] + (1 - dimDusk[0]) * falling(el, 0, dimDusk[1]) : 1;
    u.lights.value = lights * u.dusk.value;
    u.lampLights.value = lampDusk == null ? u.lights.value : lights * (lampDusk + (1 - lampDusk) * (dimDusk ? falling(el, 0, dimDusk[1]) : 1));
    const changed = state.on !== lights > 0;
    state.on = lights > 0;
    for (const k of Object.keys(shares)) u[k].value = share(shares[k], hour);
    {
      const hh = ((hour % 24) + 24) % 24;
      u.sparkle.value = sparkle && lights > 0.5 && hh >= sparkle.from - 1e-6 && hh < sparkle.to && hh - Math.floor(hh) < 5 / 60 ? 1 : 0;
    }
    const az = THREE.MathUtils.degToRad(azimuth);
    u.sunAz.value.set(Math.sin(az), -Math.cos(az));
    // twilight: faded in from 5 degrees above the horizon, its brightness falling with the sun's depth
    const tw = falling(el, 5, -1);
    const B = tw * Math.exp(Math.min(el, 0) * 0.22);                  // -6 deg: 0.27, -12: 0.07 (blue hour)
    const low = Math.exp(Math.min(el, 0) * 0.42);                      // the glow over the set sun fades faster
    // (duskGrade: g, its weight by the sun's depth; 0 at night and by day, where nothing changes)
    const g = GRADE ? smooth(el, -18, -12) : 0;
    // (duskGrade.zenith: the twilight zenith's brightness times this over the grade: a deeper blue hour sky)
    const zenK = g && GRADE.zenith != null ? 1 + g * (GRADE.zenith - 1) : 1;
    u.zenith.value.setRGB(0.04, 0.11, 0.38).multiplyScalar(B * (DUSK.zenith ?? 1) * zenK).add(c.setRGB(...SKY.zenith).multiplyScalar(lights));
    u.horizon.value.setRGB(0.3 + 0.1 * WARM, 0.31 + 0.02 * WARM, 0.38 - 0.08 * WARM).multiplyScalar(B);
    // (redder as the sun sinks; a warm dusk (dusk.warm) keeps its glow brighter and wider for longer)
    u.sunGlow.value.setRGB(1.7, 0.66, 0.18).multiplyScalar(tw * (low + WARM * 0.8 * (Math.exp(Math.min(el, 0) * 0.2) - low)))
      .multiply(c.setRGB(1, 0.75 + 0.25 * smooth(el, -6, 0), 0.6 + 0.4 * smooth(el, -6, 0)));
    u.antiGlow.value.setRGB(0.2, 0.12, 0.15).multiplyScalar(tw * smooth(el, -6 - 3 * WARM, -0.5) * (1 + 0.8 * WARM) * (DUSK.belt ?? 1));
    u.glowHeight.value = (0.03 + 0.09 * smooth(el, -10, 2)) * (1 + 0.6 * WARM);
    u.skyGlow.value.setRGB(...skyGlow).multiplyScalar(lights);   // (city.json night.skyGlow: its colour at full lights)
    u.cityGlow.value = falling(el, -2, -9);
    // the moon takes over the directional light once the sun is 2 degrees down (its own light is zero there)
    const moonK = falling(el, -2, -10);
    state.moon = el < -2;
    // the haze at night: the sky's horizon away from the sun, plus the city's glow on it
    const fog = new THREE.Color().copy(u.horizon.value).add(c.copy(u.skyGlow.value).multiplyScalar(1.06 * (ambient?.fog ?? 1)))
      .add(c.copy(u.sunGlow.value).multiplyScalar(0.12 * (DUSK.fogGlow ?? 1))).add(c.copy(u.antiGlow.value).multiplyScalar(0.2 * (DUSK.fogGlow ?? 1)));
    if (ambient?.fogTint) fog.multiply(c.setRGB(...ambient.fogTint));
    // (duskFill: the blue sky's fill while twilight lasts, fading with it)
    const fill = (duskFill ? duskFill.k * Math.min(1, B * 3) : 0) * (g ? 1 - g * (1 - GRADE.fill) : 1);
    const hemiTwilight = (0.12 + 0.1 * WARM) * B * (g ? 1 - g * (1 - GRADE.twilight) : 1);
    const hemiNight = 0.05 * lights * (ambient?.k ?? 1) + hemiTwilight + fill;
    const hemiSky = new THREE.Color(0.6, 0.6, 0.66).lerp(c.setRGB(0.42, 0.52, 0.8), WARM * Math.min(1, B * 3));
    if (ambient?.tint) hemiSky.lerp(c.setRGB(0.6, 0.6, 0.66).multiply(new THREE.Color().setRGB(...ambient.tint)), (0.05 * lights * (ambient.k ?? 1)) / Math.max(hemiNight, 1e-6));
    if (fill) hemiSky.lerp(c.setRGB(...(duskFill.colour ?? [0.45, 0.58, 1])), fill / hemiNight);
    // (duskGrade: the twilight's share of the sky light, the twilight sky's and its fill's, takes the grade's colour)
    if (g) hemiSky.lerp(c.setRGB(...GRADE.colour), g * GRADE.tint * (GRADE.whole ? 1 : Math.min(1, (hemiTwilight + fill) / Math.max(hemiNight, 1e-6))));
    // (duskGrade.moon, duskGrade.afterglow: the directional light over the grade. The moon's full cool light from high in the
    // south-east lit every roof as strongly as the whole twilight sky (London, 8 Oct: the roofs one navy slate); moon: its
    // share kept. afterglow {k, el, colour}: the bright western sky after sunset as a soft light from the sun's azimuth, el
    // degrees up (8), k times the twilight's brightness (B), in that colour (linear): the walls facing the afterglow lighter
    // than those facing away, as in blue-hour photos, instead of every unlit surface one flat tone)
    let moonLight = state.moon ? { dir: moonDir, intensity: 0.09 * moonK, color: new THREE.Color(0.66, 0.74, 1) } : null;
    if (moonLight && g && (GRADE.moon != null || GRADE.afterglow)) {
      const mk = moonLight.intensity * (1 - g * (1 - (GRADE.moon ?? 1)));
      const AG = GRADE.afterglow ? { k: 0.5, el: 8, colour: [1, 0.86, 0.74], ...GRADE.afterglow } : null;
      const ak = AG ? g * AG.k * B : 0;
      const sum = Math.max(mk + ak, 1e-6);
      const agEl = THREE.MathUtils.degToRad(AG?.el ?? 8);
      const agDir = new THREE.Vector3(Math.sin(az) * Math.cos(agEl), Math.sin(agEl), -Math.cos(az) * Math.cos(agEl));
      moonLight = { dir: moonDirGraded.copy(moonDir).multiplyScalar(mk).addScaledVector(agDir, ak).normalize(), intensity: mk + ak,
        color: new THREE.Color(0.66, 0.74, 1).multiplyScalar(mk / sum).add(c.setRGB(...(AG?.colour ?? [1, 1, 1])).multiplyScalar(ak / sum)) };
    }
    return {
      lights, changed,
      moon: moonLight,
      // how much of the day's hemisphere light and haze colour remain, and the night's own
      dayK: smooth(el, -8, 2),
      // (a warm dusk: more of the blue sky's cool fill on the walls while twilight lasts)
      hemiNight, hemiSky,
      hemiGround: new THREE.Color().setRGB(...(ambient?.ground ?? [0.8, 0.58, 0.42])),
      fog, fogDayK: smooth(el, -4, 5),
      exposure: 1 + 0.75 * falling(el, 0, -10),
    };
  }
  // (the day material of a lit copy, or the material itself: what a mesh's shaders are, whichever light is on)
  const dayMaterial = (mat) => dayOf.get(mat) ?? mat;
  // (setGrade(duskGrade): another grade for A/B from the console, then setSun again)
  return { u, extendSky, update, apply, state, dayMaterial, get grade() { return !!GRADE; }, setGrade: (dg) => { GRADE = gradeOf(dg); } };
}
