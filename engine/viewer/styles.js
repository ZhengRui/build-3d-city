// Facade styles as data: what each style in tiles.json looks like, for facade.js (and the parapets of rooftops.js).
// A viewer preset, styles/<preset>.json next to this module, holds a region's styles: per style its numbers (bay
// width, window box, shop share, ...), the groups it belongs to (masonry, lit as a home after dark, light cornice,
// ...) and the features it uses. A preset may build on another (`base`: its styles merged key by key under this
// preset's; `replace`: top-level keys taken whole from this preset, not merged), as the pipeline's presets do. The
// city picks one in city.json (facade.preset; default china-south) and may change any style without a re-pack
// (facade.styles: { "modern": { "bay": 2.9 } }); its older keys are still read: facade.acUnits (a style's `ac`) and
// night.homeStyles (`night: "home"`). A style takes another's entries where it has none of its own (`extends`:
// 'crowned' is 'stone' by day).
//
// Per style (all optional; a style without a key doesn't use that feature, a number left out takes facade.js's
// default): bay (m), window [xlo, ylo, yhi] (fractions of a bay and of a floor; null: the default), shops (a share,
// or "all"; shopsBy "hash": by its own hash, not the city's shopSeed), ac (share of windows with an air conditioner),
// cell (a patterned skin's cell, m), pattern (lattice | honeycomb | panel | portholes), zone (offices' lit zone in bays after dark,
// "office": night.windows.zone or 7), night ("home": lit as homes), masonry, mottle (brick | stone), cornice { colour:
// light | mix, scale, maxHeight, parapet: light | dark, balustrade (share) }, balconies (projecting, by column), frames
// { dark (the share of dark frames), light [r, g, b] }, glazing (sash | casement | kasten | stile | office), roof
// { flat, dormers: "every", metal: "slate", wall (the roof in the wall's colour) }, parapet (rooftops.js: village | block | low | glass | factory),
// stoneBase, windowStrips, fireEscape, billboards, monument.
// The wall's features (facade/core.js and facade.js; a share is { share, hash } of the seed, or { stripped, hash }):
// fade (the wall-detail slot: none, 'none' a branch drawn on the whole wall, 'bays' one faded with the bays),
// rustication { rows, groove, joint, depth, notShops, on: stuccoGround | stucco }, balconyRows { rows: [...], share,
// hash, shadow }, guardRails { from }, shutters, floorBands (stone | concrete), surrounds, quoins, panelSpandrels,
// stuccoGround { share, hash, paint }, polychrome, stoneBands, stoneGround, decks, brickCourses { colour, k },
// loadingDoors, shopfront (true, or { pilasters: the tint's mix }), stringCourse (stone | self), porch, reveals,
// corniceShadow { depth, k }, stucco { stripped, hash }, gruenderzeit, stringCourses, frenchBalconies, pilasters
// { every }, frieze, ceramicTiles, plattenbau, slabEdges, stoneJoints, precast, sillBands, buttresses.
// The preset may also set facade options (`facade`: windowF0, shopfront { box, doorEvery, tint, boards, letters,
// pilasters, riser, boardTop, bars { transom, mullion, fine }, interior, awnings }, roofs ...), under city.json's facade.
const isObject = (v) => v && typeof v === 'object' && !Array.isArray(v);
// objects key by key, all the way down; arrays and plain values replace (as city.js merges city.json)
const merge = (base, over) => {
  if (!isObject(base) || !isObject(over)) return over === undefined ? base : over;
  const out = { ...base };
  for (const [k, v] of Object.entries(over)) out[k] = merge(base[k], v);
  return out;
};

const cache = new Map();
// a preset with its bases merged in: { name, chain, facade, styles }
export async function loadPreset(name, url = new URL('./styles/', import.meta.url)) {
  if (!cache.has(name)) {
    cache.set(name, (async () => {
      // (with the module's own query, as main.js imports the engine's modules: a new engine version fetches its presets anew)
      const r = await fetch(new URL(`${name}.json${new URL(import.meta.url).search}`, url));
      if (!r.ok) throw new Error(`facade preset ${name}: HTTP ${r.status}`);
      const own = await r.json();
      const base = own.base ? await loadPreset(own.base, url) : { chain: [], facade: {}, styles: {} };
      const out = { name, chain: [...base.chain, name], facade: merge(base.facade, own.facade ?? {}), styles: merge(base.styles, own.styles ?? {}) };
      for (const k of own.replace ?? []) out[k] = own[k] ?? {};
      return out;
    })());
  }
  return cache.get(name);
}

// The styles of a city: { preset, chain, facade (the preset's facade options under the city's), styles: { name: data }
// for every name in tiles.json's list (a name no preset knows: {}) }. names: tiles.json styles; city: city.json merged
// (city.js loadCity), whose facade.preset, facade.styles, facade.acUnits and night.homeStyles are read.
export async function resolveStyles(names, city = {}) {
  const facade = city.facade ?? {};
  const preset = await loadPreset(facade.preset ?? 'china-south');
  // city.json over the preset: its acUnits as each style's ac, night.homeStyles as night "home", then facade.styles
  const own = {};
  for (const [name, ac] of Object.entries(facade.acUnits ?? {})) own[name] = { ac };
  for (const name of city.night?.homeStyles ?? []) own[name] = merge(own[name], { night: 'home' });
  const raw = merge(merge(preset.styles, own), facade.styles ?? {});
  // extends: the parent's entries where the style has none of its own (one level, as facade.js's PARENT was)
  const styles = Object.fromEntries(names.map((name) => {
    const s = raw[name] ?? {};
    return [name, s.extends ? merge(raw[s.extends] ?? {}, s) : s];
  }));
  const out = { preset: preset.name, chain: preset.chain, facade: facadeOptions(preset.facade, facade), styles };
  if (/[?&]facadelog=1/.test(globalThis.location?.search ?? '')) console.log('facade styles', describe(out));
  return out;
}

// The facade options: the engine's defaults < the preset's `facade` < city.json's facade (its styles and preset keys left
// out). facade: city.facade as city.js loadCity merged it, whose non-enumerable `layers` { defaults, own } keep the
// defaults and city.json's own section apart; without them (a city object built elsewhere) the merged section over the
// preset, as before.
export function facadeOptions(presetFacade = {}, facade = {}) {
  const strip = ({ styles: _s, preset: _p, ...rest }) => rest;
  const { layers } = facade;
  if (!layers) return merge(presetFacade, strip(facade));
  return merge(merge(strip(layers.defaults ?? {}), presetFacade), strip(layers.own ?? {}));
}

// the features a city's shader is built with and the styles that use each (?facadelog=1)
export function describe({ preset, chain, styles }) {
  const users = {};
  const add = (key, name) => (users[key] ??= []).push(name);
  for (const [name, s] of Object.entries(styles)) {
    for (const [k, v] of Object.entries(s)) {
      if (!['bay', 'window', 'ac', 'zone', 'extends'].includes(k)) add(k, name);
    }
  }
  return { preset, chain, users };
}
