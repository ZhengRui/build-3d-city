// The city this viewer shows: city.json in the page's own folder (the city's web/), merged over DEFAULTS.
// Everything the engine knows about a particular city comes from there or from the data indexes the
// pipeline writes (tiles.json: views, extent, styles; cars.json: types, palettes; trees.json: classes...);
// the modules themselves only hold generic defaults. The keys are documented in README.md ("city.json").
//
// Merging: objects key by key, all the way down; arrays and plain values replace the default. So a city
// only lists what differs, e.g. { "night": { "schedule": { "office": [[0, 0.1], ...] } } } replaces the
// offices' curve and keeps the other kinds'.

export const DEFAULTS = {
  title: '3D city',                // the page's title and the menu's (after nativeTitle)
  nativeTitle: '',                 // the city's name in its own script, shown first in the menu ('' for none)
  startViewPortrait: null,        // the preset a portrait screen (height > 1.2 x width) opens at instead (?view= wins)
  startView: null,                // the preset view the viewer opens at (?view= wins); null: the first in tiles.json
  about: '',                       // the menu's About text: what is real and what is invented, credits
  attribution: '',                 // an always-visible credit line (bottom right): text, [label](https://url) links, [About](#about) opens the menu's About; '' for none
  switchTitles: {},               // tooltips replacing the menu's generic ones, by switch id without 't-' (masses, lamps, trees...)
  storagePrefix: 'city3d',         // localStorage keys are `${storagePrefix}.${key}`
  location: { latitude: null, longitude: null },   // degrees (north and east positive); latitude places the sun
  // the sun's declination in degrees, or a date ('MM-DD') it is worked out from: the season the city is shown
  // in (its clearest, trees in leaf). Local solar time, so no time zone is needed
  sun: { declination: null, date: null },
  // the sky light by day (hemisphere intensity at full sun; the sun is 4) and the colour it bounces up from
  // the ground: a dense city's streets and walls throw back more than open country
  light: { sky: 1.1, ground: '#7a705e' },
  // device pixels per CSS pixel while the view moves (at most the screen's): a dense city at 2x on a laptop GPU
  // moves more smoothly at 1.25-1.5; the settled frame is drawn at full resolution
  movingResolution: 2,
  // hours: the start, and the menu's shortcuts (null: Dusk when the sun is 4.5 degrees below the horizon,
  // i.e. the blue hour). Local solar time, unless utcOffset (hours, e.g. -4 for New York's summer time) is
  // given: then clock time at that offset, turned into solar time with location.longitude and the equation of
  // time on sun.date. zone: the clock's name shown beside the time with the date (e.g. "EDT")
  // (sliderResolution: the moving frames' resolution while the time slider is dragged, null: the moving one; main.js)
  time: { start: 15.25, presets: { Day: 15.25, Dusk: null, Night: 21 }, utcOffset: null, zone: null, sliderResolution: null },
  // compass azimuth (degrees) the preset views look from: null for the sun's side of the afternoon, 200
  // (south-south-west) north of the equator and 20 south of it
  camera: { azimuth: null },        // (clear: the camera's least height over the ground, m; main.js's 10 when unset)
  // what is on at the start (URL parameters still win: ?trees=0, ?ao=0 ...; the menu changes them)
  features: { trees: true, rooftops: true, shadows: true, occlusion: true, markings: true, mirror: true, waves: true,
    traffic: true, glow: true, cityReflections: true, stats: false },
  sliders: { haze: 1, reflections: 0.5 },
  // how the first view loads (main.js; all off by default, as New York and Shenzhen were measured):
  // earlyCompile: its shaders built and compiled while the near blocks still download (from the ground and
  //   the first block in) rather than once they are all in;
  // deferLayers: the trees, rooftops and cars stream and have their shaders built only once the view is up
  //   (they come in a moment after it), so neither their downloads nor their shaders delay it;
  // frustumNear: the view waits only for the near blocks its camera sees (blocks behind it load right after);
  // passesLater: the moving frames' shaders and glass's city probe only once the first frame is on screen (until
  //   then a moving frame goes through the settled frame's pipeline, and glass reflects the sky alone)
  loading: { earlyCompile: false, deferLayers: false, frustumNear: false, passesLater: false },
  // moving water and traffic: 'settled' starts them only where the settled frame takes <= 150 ms, paced at half the
  // GPU; 'frame' measures the animating frame itself (stopped where two take > slowMs) and paces at two thirds,
  // a third after 30 s (main.js, Paris M9 round 2); overlayWater (with full): the water stays in the overlay's
  // picture of the city, drawn again over it each frame (main.js ANIM_OVERLAY_WATER; Hong Kong's white seams);
  // overlayLattice (with full): the open lattices likewise, drawn over the picture and the water (ANIM_OVERLAY_LATTICE;
  // the Eiffel Tower against the Seine); webgpuOnly: gate and full as set on WebGPU, the defaults on WebGL 2 (main.js
  // ANIM_CFG; Tokyo M9)
  animation: { gate: 'settled', slowMs: 70, full: false, reason: false, overlayWater: false, overlayLattice: false, webgpuOnly: false },
  // lighter sun shadow passes (shadows.js; off by default): groundSteep (degrees) the ground layers cast through
  // copies of their faces steeper than the sun's elevation less this; fit: tiles whose shadows can't fall in view
  // (or in the water's mirror) left out of the shadow pass
  shadows: { groundSteep: null, fit: false },
  // the building tiles' layers merged across each block, one mesh (one draw) per layer and block (main.js
  // mergeBlock), e.g. ["road", "bridge", "markings"]; ?merge=0 turns it off
  tiles: { merge: [] },
  // the SkyMesh (Preetham, with clouds)
  sky: { turbidity: 6, rayleigh: 1.6, mieCoefficient: 0.006, mieDirectionalG: 0.8, cloudCoverage: 0.55, cloudDensity: 0.55 },
  // aerial perspective: FogExp2 density per metre, its HDR colour (linear), the height (m) of the haze layer
  // (looking down from above it the haze thins) and the height (m) at which far haze is halved
  haze: { density: 7e-5, colour: [1.05, 1.18, 1.35], layer: 1500, thinHeight: 700 },
  water: {
    windFrom: 225,                 // compass direction the wind blows from: waves travel the other way
    // body colours (linear albedo): the sea's along the shore, near it, offshore, in silt plumes and in
    // enclosed basins; rivers and lakes (defaults: the Pearl River estuary and its rivers and ponds)
    sea: { shore: [0.105, 0.106, 0.082], near: [0.08, 0.094, 0.078], offshore: [0.066, 0.08, 0.082],
      silt: [0.14, 0.128, 0.088], basin: [0.048, 0.064, 0.054] },
    inland: { river: [0.036, 0.046, 0.03], lake: [0.011, 0.024, 0.018] },
    // how much of the reflected sky's colour is kept (a humid sky is paler than the clear-sky model)
    skySaturation: { sea: 0.55, inland: 0.4 },
  },
  ground: {
    airportHeading: 0,             // compass heading of the main runway: apron and taxiway panels follow it
    lawn: [[0.042, 0.07, 0.036], [0.08, 0.11, 0.055]],   // linear, darker and lighter
    aeroway: [[0.34, 0.34, 0.325], [0.42, 0.415, 0.395]],   // apron and taxiway concrete, linear, darker and lighter
    // share of street lighting districts (1.5 km cells) whose arterials, and whose small streets, have
    // sodium lamps rather than LED (expressways always do)
    sodium: { arterial: 0.4, street: 0.2 },
  },
  markings: {
    centreColour: 'yellow',        // centre lines and the median side's edge: 'yellow' (China, US) or 'white'
    // lane dividers, [period, painted] in metres, on small streets, arterials and expressways; and the
    // single dashed centre line of small two-way roads (the periods must divide the markings' along wrap)
    dashes: { street: [6, 2], arterial: [10, 4], motorway: [15, 6], centre: [10, 4] },
  },
  facade: {
    preset: null,                  // the facade styles' preset (styles.js, styles/<preset>.json); null: china-south
    styles: {},                    // changes to the preset's styles, by name and key ({ "modern": { "bay": 2.9 } })
    acUnits: {},                   // share of windows with an air conditioner under them, per style (the preset's `ac`)
    refugeShare: 0.55,             // share of towers over 150 m with refuge floors (louvred bands)
    // glass look: reflectance at grazing angles, the mirrored sky's brightness and desaturation, soft shoulder
    glass: { grazing: 0.5, skyDim: 0.65, skyDesat: 0.5, soft: 0.8, floor: 0 },
    probeHeight: 110,              // the city reflection probe's height above the orbit target's ground (m)
    // lighter probe captures (main.js; off by default): glassOnly captures only while the glass in view within glassNear m
    // of the probe covers glassShare of the screen or more; lean leaves the town masses, markings, lamps and shores out of
    // the faces, draws the tiles within reach m (nearest point) only and the ground layers within groundReach m
    probe: { glassOnly: false, glassNear: 3500, glassShare: 0.0003, lean: false, reach: 2000, groundReach: 4000 },
    // roofs: blueSteel share of factory roofs in blue steel; tones [[linear rgb, weight], ...] per building
    roofs: { blueSteel: 0.45, tones: [[[0.3, 0.3, 0.29], 1]] },
  },
  night: {
    moon: { azimuth: null, elevation: 48 },   // null: 140 (south-east) north of the equator, 40 south of it
    // share of rooms lit by the hour per kind of building (office, home, village, shops, mall, factory, civic,
    // feature), [hour, share] pairs; night.js has the defaults
    schedule: {},
  },
  // tree classes (trees.json's names) over trees.js's defaults: per class any of step, p, h, wr, mix, clump,
  // tone, thin (mix: weights of trees.js's species); species: a city's own trees in trees.js's species
  // slots (any of h, R, wK, trunkK, bark, pal, bloom, shape, leaf per slot)
  trees: { classes: {}, species: {} },
};

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
function merge(base, over) {
  if (!isObject(base) || !isObject(over)) return over === undefined ? base : over;
  const out = { ...base };
  for (const [k, v] of Object.entries(over)) out[k] = merge(base[k], v);
  return out;
}

// the year's angle (radians) at noon of a day ('MM-DD'), for Spencer's series (NOAA's solar calculator)
const yearAngle = (date) => {
  const [m, d] = date.split('-').map(Number);
  const n = Math.round((Date.UTC(2001, m - 1, d) - Date.UTC(2001, 0, 1)) / 86400000) + 1;
  return (2 * Math.PI / 365) * (n - 1 + 0.5);
};

// day of the year ('MM-DD') -> the sun's declination in degrees (to a tenth of a degree or so)
export function declinationOn(date) {
  const g = yearAngle(date);
  return (0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g)
    + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g)) * 180 / Math.PI;
}

// the equation of time on a day ('MM-DD'): apparent less mean solar time, in minutes (to about half a minute)
export function equationOfTime(date) {
  const g = yearAngle(date);
  return 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g)
    - 0.040849 * Math.sin(2 * g));
}

// local solar time (hours; or the menu's hours with shift = city.time.solarShift) -> compass azimuth and
// elevation of the sun, in degrees
export function sunAt(hours, latitude, declination, shift = 0) {
  hours += shift;
  const r = Math.PI / 180, phi = latitude * r, dec = declination * r, h = (hours - 12) * 15 * r;
  const el = Math.asin(Math.sin(phi) * Math.sin(dec) + Math.cos(phi) * Math.cos(dec) * Math.cos(h));
  const cosA = (Math.sin(dec) - Math.sin(el) * Math.sin(phi)) / (Math.cos(el) * Math.cos(phi));
  const a = Math.acos(Math.min(1, Math.max(-1, cosA))) / r;          // from north, morning side
  return { azimuth: hours > 12 ? 360 - a : a, elevation: el / r };
}

// city.json merged over DEFAULTS, with what is left open filled in (declination, dusk, the hemisphere's
// sides). A missing or broken city.json leaves the defaults, with a warning.
export async function loadCity(url = 'city.json') {
  let own = {};
  try {
    // (index.html's script has fetched city.json already, to see where three.js comes from: that response)
    const early = url === 'city.json' ? window.__cityJson : undefined;
    window.__cityJson = undefined;
    const r = await (early ?? fetch(url, { cache: 'no-cache' }));
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    own = await r.json();
  } catch (e) {
    console.warn(`city: no ${url} (${e.message}): generic defaults`);
  }
  const city = merge(DEFAULTS, own);
  // the facade options' layers kept apart (not enumerable), so styles.js can put the facade preset's options between
  // the defaults and city.json's: engine default < preset < city.json (merged here the defaults would override the preset)
  Object.defineProperty(city.facade, 'layers', { value: { defaults: DEFAULTS.facade, own: own.facade ?? {} } });
  if (city.location.latitude === null) {
    console.warn('city: city.json has no location.latitude: the sun of the equator');
    city.location.latitude = 0;
  }
  const north = city.location.latitude >= 0;
  city.sun.declination ??= city.sun.date ? declinationOn(city.sun.date) : 0;
  city.camera.azimuth ??= north ? 200 : 20;
  city.night.moon.azimuth ??= north ? 140 : 40;
  // hours the menu shows -> local solar time: none for solar time, else the longitude's and the zone's
  // difference plus the equation of time
  const { utcOffset } = city.time;
  city.time.solarShift = utcOffset === null || city.location.longitude === null ? 0
    : city.location.longitude / 15 - utcOffset + (city.sun.date ? equationOfTime(city.sun.date) / 60 : 0);
  if (city.time.presets.Dusk === null) {
    // the evening hour the sun is 4.5 degrees down, to 0.05 h (bisection: the elevation falls all afternoon)
    let lo = 12, hi = 24;
    for (let i = 0; i < 30; i++) {
      const mid = (lo + hi) / 2;
      if (sunAt(mid, city.location.latitude, city.sun.declination, city.time.solarShift).elevation > -4.5) lo = mid;
      else hi = mid;
    }
    city.time.presets.Dusk = Math.round(lo * 20) / 20;
  }
  return city;
}
