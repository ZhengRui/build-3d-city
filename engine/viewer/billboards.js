// Billboard art: an atlas of invented advertisements drawn on a canvas at startup, which the facade shader
// (facade.js, the `signs` style) samples for each board: 16 wide boards (2:1) and 16 tall ones (1:2), picked
// by the board's own shape and fitted without stretching (cropped to cover it). Five kinds, in real
// typefaces so the lettering reads as words: brand boards (a colour field, a wordmark, a tagline), show
// posters (a dark ground, a title in a display face, stars and a line of dates), product shots (a lit
// shape on a gradient, a brand and small print), portraits (a figure against a coloured backdrop, a
// headline) and news tickers (a headline band over a photo-like gradient). The names are invented; a city
// may list its own (city.json facade.billboards: {brands, shows, taglines, headlines}).
// Cost: one 2048 x 2048 texture (16 MB with mipmaps), drawn once in about 50 ms.
import * as THREE from 'three/webgpu';

const W = 2048, H = 2048;
export const ATLAS = { size: W, wide: { cols: 4, rows: 4, w: 512, h: 256 }, tall: { cols: 8, rows: 2, w: 256, h: 512, y0: 1024 } };

const DEFAULTS = {
  brands: ['NOVA', 'LUMEN', 'KESTREL', 'ORBIT', 'MAPLE & CO', 'VELO', 'ARCADIA', 'BRISK', 'HALO', 'PEAKWAY',
    'ZEPHYR', 'COBALT', 'SUNDAE', 'FIZZ', 'NORTHWIND', 'ALTO'],
  shows: ['THE LANTERN', 'MIDNIGHT CITY', 'SONG OF THE SEA', 'BROADWAY NIGHTS', 'THE GOLDEN HOUR', 'STARLIGHT',
    'HARBOR LIGHTS', 'THE LAST ACT'],
  taglines: ['Feel the city', 'Made for tomorrow', 'Taste the difference', 'Now streaming', 'Go further',
    'Open late', 'Live bright', 'New season'],
  headlines: ['MARKETS CLOSE HIGHER', 'STORM WATCH TONIGHT', 'CITY MARATHON SUNDAY', 'NEW YORK LOVES YOU',
    'WEATHER 64°F CLEAR', 'SUBWAY SERVICE UPDATE'],
};
// brand colours (sRGB)
const COLOURS = ['#c8102e', '#0033a0', '#ffc72c', '#111111', '#f4f4f2', '#00843d', '#ff6a13', '#5f259f', '#008c95',
  '#e4002b', '#1d428a', '#ffd100'];

function rng(seed) {
  let s = seed >>> 0;
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
}

// the largest font size (px) at which text fits width w
function fit(ctx, text, font, w, max) {
  let px = max;
  for (; px > 8; px -= 2) {
    ctx.font = font.replace('#', px);
    if (ctx.measureText(text).width <= w) break;
  }
  return px;
}

function brand(ctx, r, w, h, t) {
  const c1 = COLOURS[Math.floor(r() * COLOURS.length)];
  let c2 = COLOURS[Math.floor(r() * COLOURS.length)];
  if (c2 === c1) c2 = '#ffffff';
  ctx.fillStyle = c1; ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = c2; ctx.fillRect(0, h * 0.8, w, h * 0.2);
  const light = c1 === '#f4f4f2' || c1 === '#ffc72c' || c1 === '#ffd100';
  ctx.fillStyle = light ? '#111' : '#fff';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  const name = t.brands[Math.floor(r() * t.brands.length)];
  const f = r() < 0.5 ? 'bold #px Helvetica, Arial, sans-serif' : 'italic bold #px Georgia, serif';
  fit(ctx, name, f, w * 0.84, h * 0.34);
  ctx.fillText(name, w / 2, h * 0.42);
  const tag = t.taglines[Math.floor(r() * t.taglines.length)];
  fit(ctx, tag, '#px Helvetica, Arial, sans-serif', w * 0.7, h * 0.09);
  ctx.fillStyle = light ? '#111' : '#fff';
  ctx.fillText(tag, w / 2, h * 0.9);
}

function show(ctx, r, w, h, t) {
  const g = ctx.createLinearGradient(0, 0, 0, h);
  const hue = Math.floor(r() * 360);
  g.addColorStop(0, `hsl(${hue},55%,12%)`); g.addColorStop(1, `hsl(${(hue + 40) % 360},60%,4%)`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  // a spotlight and stars
  const s = ctx.createRadialGradient(w * 0.5, h * 0.35, 0, w * 0.5, h * 0.35, Math.max(w, h) * 0.55);
  s.addColorStop(0, `hsla(${(hue + 180) % 360},80%,70%,0.55)`); s.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = s; ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = 'rgba(255,240,200,0.8)';
  for (let i = 0; i < 40; i++) ctx.fillRect(r() * w, r() * h * 0.5, 2, 2);
  const title = t.shows[Math.floor(r() * t.shows.length)];
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillStyle = `hsl(${(hue + 30) % 360},90%,72%)`;
  const words = title.split(' ');
  const tall = h > w;
  const lines = tall && words.length > 1 ? [words.slice(0, Math.ceil(words.length / 2)).join(' '), words.slice(Math.ceil(words.length / 2)).join(' ')] : [title];
  const px = Math.min(...lines.map((l) => fit(ctx, l, 'bold #px Georgia, "Times New Roman", serif', w * 0.88, h * (tall ? 0.13 : 0.3))));
  ctx.font = `bold ${px}px Georgia, "Times New Roman", serif`;
  lines.forEach((l, i) => ctx.fillText(l, w / 2, h * 0.55 + (i - (lines.length - 1) / 2) * px * 1.1));
  ctx.fillStyle = '#f2e6c8';
  fit(ctx, 'NOW PLAYING · TICKETS', 'bold #px Helvetica, Arial, sans-serif', w * 0.7, h * 0.07);
  ctx.fillText('NOW PLAYING · TICKETS', w / 2, h * 0.88);
}

function product(ctx, r, w, h, t) {
  const hue = Math.floor(r() * 360);
  const g = ctx.createLinearGradient(0, 0, w, h);
  g.addColorStop(0, `hsl(${hue},70%,${20 + r() * 30}%)`); g.addColorStop(1, `hsl(${(hue + 60) % 360},70%,8%)`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  // the product: a phone, a bottle or a can, lit from the side
  const kind = Math.floor(r() * 3);
  const cx = w * (0.28 + r() * 0.1), cy = h * 0.52, sh = h * 0.7, sw = kind === 0 ? sh * 0.48 : kind === 1 ? sh * 0.3 : sh * 0.36;
  const lg = ctx.createLinearGradient(cx - sw / 2, 0, cx + sw / 2, 0);
  lg.addColorStop(0, '#222'); lg.addColorStop(0.35, kind === 0 ? '#9ab' : `hsl(${(hue + 180) % 360},80%,55%)`); lg.addColorStop(1, '#111');
  ctx.fillStyle = lg;
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(cx - sw / 2, cy - sh / 2, sw, sh, kind === 0 ? sw * 0.15 : sw * 0.35);
  else ctx.rect(cx - sw / 2, cy - sh / 2, sw, sh);
  ctx.fill();
  if (kind === 0) { ctx.fillStyle = `hsl(${hue},60%,45%)`; ctx.fillRect(cx - sw * 0.42, cy - sh * 0.44, sw * 0.84, sh * 0.86); }
  ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#fff';
  const name = t.brands[Math.floor(r() * t.brands.length)];
  const x0 = cx + sw / 2 + w * 0.05, tw = w - x0 - w * 0.05;
  if (tw > w * 0.2) {
    fit(ctx, name, 'bold #px Helvetica, Arial, sans-serif', tw, h * 0.22);
    ctx.fillText(name, x0, h * 0.42);
    const tag = t.taglines[Math.floor(r() * t.taglines.length)];
    fit(ctx, tag, '#px Helvetica, Arial, sans-serif', tw, h * 0.08);
    ctx.fillStyle = 'rgba(255,255,255,0.85)';
    ctx.fillText(tag, x0, h * 0.62);
  } else {
    ctx.textAlign = 'center';
    fit(ctx, name, 'bold #px Helvetica, Arial, sans-serif', w * 0.9, h * 0.1);
    ctx.fillText(name, w / 2, h * 0.93);
  }
}

function portrait(ctx, r, w, h, t) {
  const hue = Math.floor(r() * 360);
  const g = ctx.createRadialGradient(w * 0.65, h * 0.4, 0, w * 0.65, h * 0.4, Math.max(w, h));
  g.addColorStop(0, `hsl(${hue},45%,62%)`); g.addColorStop(1, `hsl(${(hue + 30) % 360},50%,18%)`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  // a figure, head and shoulders, softly shaded
  const left = r() < 0.5;
  const fx = w * (left ? 0.3 : 0.7), s = Math.min(w * 0.5, h * 0.9);
  const skin = [`hsl(28,45%,${62 + r() * 12}%)`, `hsl(25,40%,${40 + r() * 10}%)`, `hsl(22,35%,${24 + r() * 8}%)`][Math.floor(r() * 3)];
  const cloth = `hsl(${(hue + 180 + r() * 60) % 360},40%,${15 + r() * 30}%)`;
  ctx.fillStyle = cloth;
  ctx.beginPath(); ctx.ellipse(fx, h * 1.02, s * 0.5, s * 0.42, 0, Math.PI, 0); ctx.fill();
  ctx.fillStyle = skin;
  ctx.fillRect(fx - s * 0.07, h * 0.58, s * 0.14, s * 0.2);
  ctx.beginPath(); ctx.ellipse(fx, h * 0.45, s * 0.16, s * 0.21, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = ['#1a1310', '#3b2618', '#6b4a2b', '#c9a36a'][Math.floor(r() * 4)];
  ctx.beginPath(); ctx.ellipse(fx, h * 0.37, s * 0.18, s * 0.14, 0, Math.PI, 0); ctx.fill();
  const shade = ctx.createLinearGradient(fx - s * 0.2, 0, fx + s * 0.2, 0);
  shade.addColorStop(0, 'rgba(0,0,0,0)'); shade.addColorStop(1, 'rgba(0,0,0,0.3)');
  ctx.fillStyle = shade; ctx.fillRect(fx - s * 0.2, h * 0.2, s * 0.4, h * 0.5);
  ctx.textAlign = left ? 'right' : 'left'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#fff';
  const tx = left ? w * 0.94 : w * 0.06, tw = w * 0.5;
  const name = t.brands[Math.floor(r() * t.brands.length)];
  if (w > h) {
    fit(ctx, name, 'bold #px Helvetica, Arial, sans-serif', tw, h * 0.24);
    ctx.fillText(name, tx, h * 0.4);
    const tag = t.taglines[Math.floor(r() * t.taglines.length)];
    fit(ctx, tag, 'italic #px Georgia, serif', tw, h * 0.1);
    ctx.fillText(tag, tx, h * 0.62);
  } else {
    ctx.textAlign = 'center';
    fit(ctx, name, 'bold #px Helvetica, Arial, sans-serif', w * 0.9, h * 0.1);
    ctx.fillText(name, w / 2, h * 0.1);
  }
}

function ticker(ctx, r, w, h, t) {
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, '#1b2a44'); g.addColorStop(1, '#0a1020');
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = '#c8102e'; ctx.fillRect(0, h * 0.62, w * 0.22, h * 0.26);
  ctx.fillStyle = '#f4f4f2'; ctx.fillRect(w * 0.22, h * 0.62, w * 0.78, h * 0.26);
  ctx.textBaseline = 'middle'; ctx.textAlign = 'center'; ctx.fillStyle = '#fff';
  fit(ctx, 'NEWS', 'bold #px Helvetica, Arial, sans-serif', w * 0.18, h * 0.16);
  ctx.fillText('NEWS', w * 0.11, h * 0.75);
  ctx.textAlign = 'left'; ctx.fillStyle = '#111';
  const head = t.headlines[Math.floor(r() * t.headlines.length)];
  fit(ctx, head, 'bold #px Helvetica, Arial, sans-serif', w * 0.74, h * 0.16);
  ctx.fillText(head, w * 0.25, h * 0.75);
  ctx.fillStyle = '#9fb3d9';
  fit(ctx, 'LIVE · 24 HOURS', 'bold #px Helvetica, Arial, sans-serif', w * 0.5, h * 0.12);
  ctx.fillText('LIVE · 24 HOURS', w * 0.06, h * 0.3);
}

const KINDS = [brand, show, product, brand, portrait, ticker, show, product];

export function makeBillboardAtlas(texts = {}) {
  const t = { ...DEFAULTS, ...texts };
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#222'; ctx.fillRect(0, 0, W, H);
  const r = rng(20261010);
  const draw = (x, y, w, h, i) => {
    ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip(); ctx.translate(x, y);
    KINDS[i % KINDS.length](ctx, r, w, h, t);
    ctx.restore();
  };
  const { wide, tall } = ATLAS;
  for (let i = 0; i < wide.cols * wide.rows; i++) draw((i % wide.cols) * wide.w, Math.floor(i / wide.cols) * wide.h, wide.w, wide.h, i);
  for (let i = 0; i < tall.cols * tall.rows; i++) draw((i % tall.cols) * tall.w, tall.y0 + Math.floor(i / tall.cols) * tall.h, tall.w, tall.h, i + 3);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.generateMipmaps = true;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.anisotropy = 4;
  return tex;
}
