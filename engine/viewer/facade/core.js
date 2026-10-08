// The facade's core features, one implementation each, for any city whose styles list them (styles.js, the presets in
// styles/*.json): node helpers, and per feature a function that builds its nodes from a context `c` of the facade's
// shared nodes (the top level's, or a wall-detail branch's copies: facade.js) and the feature's parameters. Each
// returns the feature's mask or colour; the caller lays it over the wall in its slot's order (facade.js), so a city's
// layers come in the order it was drawn before the merge (London's courses after its bands, Berlin's inside its brick
// branch...). Numbers are the presets'.
import { float as tslFloat, vec3, select, mix, smoothstep, max, min, abs, floor, fract, clamp, fwidth, hash } from 'three/tsl';

// ---------------------------------------------------------------- helpers
// a float constant: one node per value, shared by every use (a constant is written into the shader where it's used,
// never a variable: sharing it only spares the node builder hundreds of nodes; a node is converted as before)
const consts = new Map();
export const float = (v) => {
  if (typeof v !== 'number') return tslFloat(v);
  let n = consts.get(v);
  if (!n) consts.set(v, (n = tslFloat(v)));
  return n;
};
// per-style constant, picked by the style id with a chain of selects
export const pick = (style, values) => {
  let r = float(values[values.length - 1]);
  for (let i = values.length - 2; i >= 0; i--) r = select(style.lessThan(i + 0.5), float(values[i]), r);
  return r;
};
// branchless choice. TSL compiles a select between two non-trivial branches into an if/else, and a
// node first built inside one branch is then declared in that branch's scope, so the other reads it
// uninitialised (black); mixing with a 0/1 weight keeps every node at the top level.
export const f01 = (c) => select(c, float(1), float(0));
export const sel = (c, a, b) => mix(b, a, f01(c));
// 1 inside [lo, hi], 0 outside, with edges softened over w (anti-aliasing)
export const band = (t, lo, hi, w) => smoothstep(lo.sub(w), lo.add(w), t).mul(float(1).sub(smoothstep(hi.sub(w), hi.add(w), t)));
// 1 near whole numbers of t (lines of half-width w), anti-aliased
export const lines = (t, w) => {
  const aa = max(fwidth(t), 0.001);
  return smoothstep(float(0.5).sub(w).sub(aa), float(0.5).sub(w).add(aa), abs(fract(t).sub(0.5)));
};
// the share of [t - w/2, t + w/2] where fract(t) lies in [lo, hi]: an exact box filter of a periodic
// stripe, from its integral. Sharp when a period covers many pixels, its average (hi - lo) when it is
// smaller than one, and never shimmering in between (the stripes keep reading as texture as they shrink)
const stripeInt = (t, lo, hi) => floor(t).mul(hi.sub(lo)).add(clamp(fract(t), lo, hi)).sub(lo);
export const stripe = (t, lo, hi, w) => stripeInt(t.add(w.mul(0.5)), lo, hi).sub(stripeInt(t.sub(w.mul(0.5)), lo, hi)).div(w);
export const h1 = (x) => hash(x);
export const hash2 = (a, b) => hash(a.mul(12.9898).add(b.mul(78.233)));
export const rgb = (c) => vec3(...c);
// a colour from a list of [threshold, colour] by a 0..1 value: the first whose threshold the value is under, else the last
export const palette = (t, list) => list.slice(0, -1).reduceRight((r, [k, c]) => sel(t.lessThan(k), rgb(c), r), rgb(list.at(-1)[1]));
// a test on one style's buildings: all of them, or a share by hash k of the seed (`share`: under it; `stripped`: that
// share left out, over it)
export const shareOf = (test, seed, { share = 1, stripped = 0, hash: k = 0 } = {}) => {
  if (stripped) return test.and(h1(seed.mul(k)).greaterThan(stripped));
  return share === 1 || share === true ? test : test.and(h1(seed.mul(k)).lessThan(share));
};
// a band of the floor relative to the window box: at 'sill' (from ylo + a to ylo + b), 'lintel' (yhi + a .. yhi + b)
// or the floor's own fractions; a 0 offset is the edge itself
const edge = (base, d) => (d === 0 ? base : d < 0 ? base.sub(-d) : base.add(d));
export const bandAt = (c, at, a, b) => (at === 'sill' ? band(c.cy, edge(c.ylo, a), edge(c.ylo, b), c.wy)
  : at === 'lintel' ? band(c.cy, edge(c.yhi, a), edge(c.yhi, b), c.wy) : band(c.cy, float(a), float(b), c.wy));

// ---------------------------------------------------------------- rustication
// grooves every `groove` m, `joint` of it the groove (box-filtered); the caller darkens the wall by the mask x depth
export const rusticJoints = (c, { groove, joint }) => stripe(c.y.div(groove), float(0), float(joint), c.fyM.div(groove));

// ---------------------------------------------------------------- brick courses
// bed joints every 75 mm, head joints every 225 mm in stretcher bond (box-filtered), faded out before they shimmer:
// the joints, and their fade by the courses' size on screen (fs: metres per pixel along the wall)
export const brickJoints = (c) => {
  const bed = stripe(c.y.div(0.075), float(0), float(0.14), c.fyM.div(0.075));
  const head = stripe(c.s.div(0.225).add(floor(c.y.div(0.075)).mod(2).mul(0.5)), float(0), float(0.05), c.fs.div(0.225));
  return clamp(bed.add(head), 0, 1);
};
export const brickRes = (fyM, fs) => float(1).sub(smoothstep(float(0.12), float(0.45), max(fyM.div(0.075), fs.div(0.225))));
// the courses over w: mortar of the given colour, k strong (mask: the styles' test, where the slot has no branch of its own)
export const brickCourses = (w, c, { colour, k }, mask = null) => {
  let t = brickJoints(c).mul(c.res);
  if (mask) t = t.mul(mask);
  return mix(w, rgb(colour), t.mul(k));
};

// ---------------------------------------------------------------- the cornice's shadow
// the band of wall under the cornice that its projection shades, `depth` m deep
export const corniceShadow = (c, depth) => {
  const under = c.wallH.sub(c.corniceH);
  return band(c.y, under.sub(depth), under, c.fyM);
};

// ---------------------------------------------------------------- shopfronts
// The ground floor's shops (facade.shopfront, a preset's: London's, Berlin's), its layers in this order over w, each
// optional: tint (the whole front a pale pilaster colour, k strong; `pilasterK`: the style's mix towards it), boards
// (a fascia across `band` of the floor, its colour per shop of two bays from `colours`), letters (the shop's name on
// the board), pilasters (light strips between the shops), riser (a dark stall riser under the windows), boardTop (a
// lit moulding over the board). gate: the ground floor's mask where the slot isn't already a branch of shop floors.
export const shopfront = (w, c, sf, { gate = null, pilasterK = null, light = null } = {}) => {
  const g = (m) => (gate ? gate.mul(m) : m);
  const shopX = c.col.div(2);
  let tintC = null;
  if (sf.tint) {
    tintC = mix(c.wall, rgb(sf.tint.colour), pilasterK ?? float(sf.tint.pilasters));
    w = mix(w, tintC, gate ? gate.mul(sf.tint.k) : float(sf.tint.k));
  }
  let fascia = null;
  if (sf.boards) {
    const shopId = h1(floor(shopX).add(c.seed.mul(71.9)));
    const fasciaC = palette(shopId, sf.boards.colours);
    fascia = g(band(c.cy, float(sf.boards.band[0]), float(sf.boards.band[1]), c.wy));
    w = mix(w, fasciaC, fascia);
    if (sf.letters) w = mix(w, shopLetters(c, shopX, shopId), shopLetterMask(c, shopX).mul(fascia));
  }
  if (sf.pilasters) {
    const p = sf.pilasters;
    const pil = band(fract(shopX.add(p.at)), float(p.band[0]), float(p.band[1]), c.wx.mul(0.5));
    w = mix(w, light(c.wall), pil.mul(float(1).sub(fascia)).mul(p.k));
  }
  if (sf.riser) {
    const riser = g(float(1).sub(smoothstep(float(sf.riser.to[0]), float(sf.riser.to[1]), c.cy)));
    w = mix(w, rgb(sf.riser.colour), riser);
  }
  if (sf.boardTop) w = mix(w, tintC.mul(sf.boardTop.k), g(band(c.cy, float(sf.boardTop.band[0]), float(sf.boardTop.band[1]), c.wy)));
  return w;
};
// (Berlin M4 fix round) the shop's name on its board: light letters on dark and coloured boards, dark on light: 0.24 m
// cells, four in five a glyph (a block with a counter or a notch cut out of it, by its hash), within the middle 70 % of
// the shop's two bays; far away their average
const shopLetters = (c, shopX, shopId) => {
  const darkBoard = shopId.lessThan(0.56).or(shopId.greaterThan(0.84));
  return sel(darkBoard, sel(h1(c.seed.mul(13.1).add(floor(shopX))).lessThan(0.7), vec3(0.85, 0.84, 0.8), vec3(0.75, 0.55, 0.08)), vec3(0.05, 0.05, 0.06));
};
const shopLetterMask = (c, shopX) => {
  const u = fract(shopX);
  const lu = fract(c.s.div(0.24)), lk = h1(floor(c.s.div(0.24)).add(c.seed.mul(17.3)));
  const lv = c.cy.sub(0.882).div(0.066), dlu = c.fs.div(0.24), dlv = c.wy.div(0.066);
  const counter = band(lu, float(0.4), sel(lk.lessThan(0.4), float(0.6), float(0.95)), dlu).mul(band(lv, float(0.3), float(0.7), dlv));
  const glyph = band(lu, float(0.16), float(0.84), dlu).mul(float(1).sub(counter.mul(c.fineRes)));
  return glyph.mul(f01(lk.lessThan(0.8))).mul(c.fineRes.mul(0.4).add(0.6))
    .mul(band(u, float(0.15), float(0.85), c.wx.mul(0.5))).mul(band(lv, float(0), float(1), dlv));
};

// ---------------------------------------------------------------- glazing
// a window's own coordinates (V: the near branch's copies): its box's width and height in the bay's and floor's
// fractions, the point's place in it (wu, wv 0..1), their size per pixel, and `fine`: 1 while the glazing bars are
// resolved, fading out between the given sizes (sash bars 0.04-0.12, Kastenfenster 0.05-0.14)
export const windowCoords = (V, fineFrom, fineTo) => {
  const ww = max(V.xhi.sub(V.xlo), 0.05), wh = max(V.yhi.sub(V.ylo), 0.05);
  const wu = V.cx.sub(V.xlo).div(ww), wv = V.cy.sub(V.ylo).div(wh);
  const du = max(V.wx.div(ww), 1e-4), dv = max(V.wy.div(wh), 1e-4);
  const fine = float(1).sub(smoothstep(float(fineFrom), float(fineTo), max(du, dv)));
  return { wu, wv, du, dv, fine };
};

// ---------------------------------------------------------------- window bars (the glazing types)
// The bars of a window (wc: windowCoords), by glazing type, box-filtered and faded by `fine`, and the shop windows'
// transom and mullion. sash (London's sashes and Portland's casements, a per-pixel choice: V.sash 1 sash six over six
// with a meeting rail, 2 casement two lights under a transom; lights [v, h] per type), kasten (Berlin's Kastenfenster:
// a meeting stile at stileAt and a transom at tr; post-war windows a stile at two thirds, `old` false). gate: the
// windows that have them.
export const windowBars = (wc, type, o) => {
  const { wu, wv, du, dv, fine } = wc;
  if (type === 'sash') {
    const stoneW = o.sash.greaterThan(1.5);
    const nv = sel(stoneW, float(2), float(3)), nh = sel(stoneW, float(1.4), float(4));
    const rail = stripe(wv.mul(2).add(0.04), float(0), float(0.08), dv.mul(2)).mul(f01(stoneW.not()));
    const vbar = stripe(wu.mul(nv).add(0.03), float(0), float(0.06), du.mul(nv)).mul(fine);
    const hbar = stripe(wv.mul(nh).add(0.03), float(0), float(0.06), dv.mul(nh)).mul(fine);
    return clamp(rail.add(vbar).add(hbar), 0, 1).mul(min(o.sash, 1)).mul(o.gate);
  }
  const stile = stripe(wu.sub(o.stileAt).add(0.5), float(0.47), float(0.53), du);
  const transom = f01(o.old).mul(stripe(wv.sub(o.tr).add(0.5), float(0.475), float(0.525), dv));
  return clamp(stile.add(transom), 0, 1).mul(fine).mul(o.gate);
};
// a shop window's transom (`transom` [lo, hi] of its height, under clerestory lights) and middle mullion (`mullion`
// [offset, width]), faded by `fine` where the preset says so (facade.shopfront.bars)
export const shopWindowBars = (wc, { transom, mullion, fine: fade }, gate) => {
  const { wu, wv, du, dv, fine } = wc;
  const sv = stripe(wv.add(0.03), float(transom[0]), float(transom[1]), dv)
    .add(stripe(wu.mul(2).add(mullion[0]), float(0), float(mullion[1]), du.mul(2)).mul(f01(wv.lessThan(0.97))));
  return fade ? clamp(sv, 0, 1).mul(fine).mul(gate) : clamp(sv, 0, 1).mul(gate);
};
