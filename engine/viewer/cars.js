// Cars: moving traffic and parked cars (06d_cars.py). Which way traffic drives is in the lanes' data.
//
// Data: per 1 km tile, lanes (polylines with a speed and a queue profile) holding moving cars, and parked
// cars (kerbside rows, car parks, bus stations). A moving car is only a place in its lane's loop: at time t
// it is at p = (p0 + v t) mod P in the lane's free coordinate, which a speed profile maps to the distance
// along the lane (slowing to a crawl at the stop line of a signalled junction, speeding up beyond it), so
// cars bunch into queues and pull away without any simulation. Lanes end a few metres inside the junction
// boxes, where cars fade out (and fade in at the start), dithered.
//
// Look: low-poly types built here at startup to 06d_cars.py's sizes and colours (cars.json: sedan, SUV,
// taxi with a roof sign (Shenzhen's BYD e6), MPV/van, bus, box truck, tractor with a 40 ft container; a type
// of another name is drawn as a sedan; a type's "model" picks a variant: hatch (a two-box hatchback),
// taxi_paris (dark, the white roof light with its green or red lamp), bus_idfm (Île-de-France Mobilités'
// livery), taxi_london (the LEVC TX black cab), bus_london (a red double-decker), bus_art (an articulated bus), tram_cab / tram_mid / tram_tail (a tram's modules,
// 06d_cars [cars.trams]), moto (a scooter and its rider, left off when parked)), about 200 triangles each (the
// lorry with its ten wheels 460): a body lofted through cross-sections (bumper, hood, windscreen, roof, rear
// window, boot), wheels, lights. One procedural material (TSL): paint in the car's colours (a second colour for taxi roofs, bus liveries, cargo
// boxes and containers, container corrugation), dark glass and a clear-coat that reflect the sky (Fresnel,
// like the facades' glass), tyres, lights. Beyond NEAR m a car is a box painted the same way (window band,
// dark windscreen seen from above), beyond FAR none.
// After dark (night.js's uniforms) moving cars have their lights on: headlamps and red tail lights on the
// models, and on the boxes' front and rear faces (with a trace of both on the roof, what their beams light
// ahead and behind as seen from above), bright enough that a far car stays a white or red point, the colour
// by which way it faces the camera. Parked cars stay dark.
// Shadows: the sun's shadow map is not redrawn while traffic moves (it would cost a scene pass per frame),
// so cars don't cast into it. Each car within SHADOW m instead gets a planar shadow: a convex proxy of the
// car (body box and cabin) squashed onto the road along the sun direction. Projected like that, the
// faces lit by the sun come out counter-clockwise seen from above and the others clockwise, so back-face
// culling leaves exactly one layer of shadow: one translucent draw for all cars, no stencil.
//
// Motion: update(time) rewrites the pose (position, heading, fade) of the cars on lanes within ANIM m of
// the camera, choosing each one's level of detail as it goes; cars on lanes further away and parked cars
// are written once per refill (when the camera has moved). Poses and looks are instance attributes (two
// vec4 per car) that the vertex shader turns into the transform. Draw calls: one per type near + far boxes +
// shadows.
import * as THREE from 'three/webgpu';
import {
  attribute, uniform, uniformArray, vec2, vec3, float, int, cos, sin, floor, fract, pow, mix, select, dot,
  transformNormalToView, varying, positionWorld, normalView, positionViewDirection, reflectVector,
  pmremTexture, screenCoordinate, smoothstep, max, shadow, fwidth, abs, clamp,
} from 'three/tsl';

const NEAR = 320;                // full models within this distance (m), boxes beyond
const FAR = 3000, FAR_FADE = 500; // no cars beyond FAR; the last FAR_FADE m dissolve
const ANIM = 1500;               // cars on lanes within this distance move every frame
const SHADOW = 1000;             // planar shadows within this distance
const LOAD = 4200, DROP = 5600;  // tiles loaded within LOAD m of the camera, dropped beyond DROP
const CONCURRENCY = 4;
const REFILL_MS = 150;

// ---------------------------------------------------------------- models
// Parts (vertex attribute): 0 paint, 1 second colour, 2 glass, 3 tyre and black plastic, 4 headlight,
// 5 tail light, 6 grey trim (hubs, chassis), 7 taxi sign, 8 a two-wheeler's rider (dark clothes), 9 the rider's
// helmet (second colour), 10 white roof light (Paris's "TAXI PARISIEN"), 11 its green (free) or red (taken) lamp,
// 12 chrome (pale grey, shiny: the London cab's grille). Riders (8, 9) are left out on parked two-wheelers.
const PAINT = 0, PAINT2 = 1, GLASS = 2, TYRE = 3, HEAD = 4, TAIL = 5, TRIM = 6, SIGN = 7, RIDER = 8, HELMET = 9,
  SIGN_W = 10, LAMP = 11, CHROME = 12;

class Builder {
  constructor() { this.pos = []; this.nrm = []; this.part = []; }
  // a triangle facing away from `ref` (the inside of the solid)
  tri(a, b, c, part, ref) {
    const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    let n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    const len = Math.hypot(...n);
    if (len < 1e-7) return;
    n = n.map((x) => x / len);
    const m = [(a[0] + b[0] + c[0]) / 3 - ref[0], (a[1] + b[1] + c[1]) / 3 - ref[1], (a[2] + b[2] + c[2]) / 3 - ref[2]];
    if (n[0] * m[0] + n[1] * m[1] + n[2] * m[2] < 0) { [b, c] = [c, b]; n = n.map((x) => -x); }
    for (const p of [a, b, c]) { this.pos.push(...p); this.nrm.push(...n); this.part.push(part); }
  }
  quad(a, b, c, d, part, ref) { this.tri(a, b, c, part, ref); this.tri(a, c, d, part, ref); }
  // a body lofted through stations {x, pts: [[halfWidth, y], ...] bottom to top}; part(i, j) for the
  // strip j (sides 0..m-1, top m) between stations i and i+1, cap(end, j) for the end faces
  loft(stations, part, cap, refY) {
    const m = stations[0].pts.length - 1;
    for (let i = 0; i < stations.length - 1; i++) {
      const A = stations[i], B = stations[i + 1];
      const ref = [(A.x + B.x) / 2, refY, 0];
      for (let j = 0; j < m; j++) {
        for (const s of [1, -1]) {
          this.quad([A.x, A.pts[j][1], s * A.pts[j][0]], [B.x, B.pts[j][1], s * B.pts[j][0]],
            [B.x, B.pts[j + 1][1], s * B.pts[j + 1][0]], [A.x, A.pts[j + 1][1], s * A.pts[j + 1][0]], part(i, j), ref);
        }
      }
      const [wa, ya] = A.pts[m], [wb, yb] = B.pts[m];
      this.quad([A.x, ya, wa], [B.x, yb, wb], [B.x, yb, -wb], [A.x, ya, -wa], part(i, m), ref);
    }
    // end faces: the reference point inside the body, a metre in from the end station (stations run
    // front to back, in either direction), so the faces point out
    const inward = Math.sign(stations[stations.length - 1].x - stations[0].x) || 1;
    for (const [end, S, dir] of [[0, stations[0], inward], [1, stations[stations.length - 1], -inward]]) {
      const ref = [S.x + dir, refY, 0];
      for (let j = 0; j < m; j++) {
        const [w0, y0] = S.pts[j], [w1, y1] = S.pts[j + 1];
        this.quad([S.x, y0, w0], [S.x, y0, -w0], [S.x, y1, -w1], [S.x, y1, w1], cap(end, j), ref);
      }
    }
  }
  box(x0, x1, y0, y1, w, part) {
    this.loft([{ x: x1, pts: [[w, y0], [w, y1]] }, { x: x0, pts: [[w, y0], [w, y1]] }], () => part, () => part, (y0 + y1) / 2);
  }
  // a box along the segment a -> b in the x-y plane (a limb): thickness 2 hh across it, z from zc - hw to zc + hw
  beam(a, b, zc, hw, hh, part) {
    const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy), nx = -dy / l * hh, ny = dx / l * hh;
    const c = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, zc];
    const P = (p, s, z) => [p[0] + s * nx, p[1] + s * ny, zc + z * hw];
    const v = [P(a, -1, -1), P(b, -1, -1), P(b, 1, -1), P(a, 1, -1), P(a, -1, 1), P(b, -1, 1), P(b, 1, 1), P(a, 1, 1)];
    for (const [i, j, k, m] of [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [3, 2, 6, 7], [0, 3, 7, 4], [1, 2, 6, 5]]) {
      this.quad(v[i], v[j], v[k], v[m], part, c);
    }
  }
  // one wheel in the middle (a two-wheeler's): tread and both faces, a 10-gon
  wheel1(x, r, w) {
    const N = 10, ring = (k) => [x + r * Math.cos((k + 0.5) * 2 * Math.PI / N), r + r * Math.sin((k + 0.5) * 2 * Math.PI / N)];
    for (let k = 0; k < N; k++) {
      const [xa, ya] = ring(k), [xb, yb] = ring(k + 1);
      this.quad([xa, ya, w], [xb, yb, w], [xb, yb, -w], [xa, ya, -w], TYRE, [x, r, 0]);
      for (const s of [1, -1]) this.tri([x, r, s * w], [xa, ya, s * w], [xb, yb, s * w], k % 5 ? TYRE : TRIM, [x, r, 0]);
    }
  }
  // a wheel on each side at x: tread and outer face (14-gon), a grey hub; its outer face at zOut
  wheels(x, r, zOut, width = 0.24) {
    const N = 14;
    for (const s of [1, -1]) {
      const zo = s * zOut, zi = s * (zOut - width), axis = [x, r, s * (zOut - width / 2)];
      const ring = (k, rr = r) => [x + rr * Math.cos((k + 0.5) * 2 * Math.PI / N), r + rr * Math.sin((k + 0.5) * 2 * Math.PI / N)];
      for (let k = 0; k < N; k++) {
        const [xa, ya] = ring(k), [xb, yb] = ring(k + 1);
        this.quad([xa, ya, zo], [xb, yb, zo], [xb, yb, zi], [xa, ya, zi], TYRE, axis);
        this.tri([x, r, zo], [xa, ya, zo], [xb, yb, zo], TYRE, [x, r, zi]);
        const [ha, hb] = [ring(k, r * 0.58), ring(k + 1, r * 0.58)];
        this.tri([x, r, zo + s * 0.006], [ha[0], ha[1], zo + s * 0.006], [hb[0], hb[1], zo + s * 0.006], TRIM, [x, r, zi]);
      }
    }
  }
  // lights: a quad each side on an end face at x, facing +x (front) or -x (rear)
  lights(x, y0, y1, z0, z1, part) {
    const dir = Math.sign(x);
    for (const s of [1, -1]) {
      this.quad([x, y0, s * z0], [x, y0, s * z1], [x, y1, s * z1], [x, y1, s * z0], part, [x - dir, (y0 + y1) / 2, 0]);
    }
  }
  // smooth shading across edges flatter than `crease` degrees (a rounded body, bevelled edges), faceted beyond
  smooth(crease = 42) {
    const cos = Math.cos(crease * Math.PI / 180), P = this.pos, N = this.nrm, n = P.length / 3;
    const key = (i) => `${Math.round(P[3 * i] * 500)},${Math.round(P[3 * i + 1] * 500)},${Math.round(P[3 * i + 2] * 500)}`;
    const groups = new Map();
    for (let i = 0; i < n; i++) { const k = key(i); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(i); }
    const face = N.slice(), out = N.slice();
    for (const ids of groups.values()) {
      for (const i of ids) {
        let x = 0, y = 0, z = 0;
        for (const j of ids) {
          const d = face[3 * i] * face[3 * j] + face[3 * i + 1] * face[3 * j + 1] + face[3 * i + 2] * face[3 * j + 2];
          if (d >= cos) { x += face[3 * j]; y += face[3 * j + 1]; z += face[3 * j + 2]; }
        }
        const l = Math.hypot(x, y, z) || 1;
        out[3 * i] = x / l; out[3 * i + 1] = y / l; out[3 * i + 2] = z / l;
      }
    }
    this.nrm = out;
    return this;
  }
  geometry() {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(this.nrm, 3));
    g.setAttribute('part', new THREE.Float32BufferAttribute(this.part, 1));
    return g;
  }
}

// three-box and two-box cars: stations of [half width, y] at the sill, the shoulder and the top.
// Segment roles: glass for windscreen and rear window (top and sides), roof (second colour) with glass sides
const S = (x, pts) => ({ x, pts });
const MODELS = {
  sedan: {
    stations: [S(2.375, [[0.8, 0.3], [0.8, 0.62], [0.66, 0.68]]), S(2.15, [[0.9, 0.18], [0.9, 0.78], [0.76, 0.84]]),
      S(0.95, [[0.91, 0.18], [0.91, 0.9], [0.8, 0.96]]), S(0.1, [[0.91, 0.18], [0.91, 0.94], [0.64, 1.44]]),
      S(-0.95, [[0.91, 0.18], [0.91, 0.95], [0.64, 1.44]]), S(-1.72, [[0.9, 0.18], [0.9, 0.96], [0.76, 1.02]]),
      S(-2.28, [[0.86, 0.22], [0.86, 0.94], [0.74, 0.99]]), S(-2.375, [[0.78, 0.32], [0.78, 0.84], [0.66, 0.88]])],
    glass: [2, 4], roof: 3, wheels: { x: [1.42, -1.38], r: 0.32 }, head: [0.5, 0.62, 0.42, 0.72], tail: [0.66, 0.8, 0.44, 0.74],
  },
  suv: {
    stations: [S(2.35, [[0.86, 0.36], [0.86, 0.78], [0.72, 0.86]]), S(2.08, [[0.95, 0.24], [0.95, 0.96], [0.82, 1.02]]),
      S(1.05, [[0.95, 0.24], [0.95, 1.06], [0.84, 1.12]]), S(0.3, [[0.95, 0.24], [0.95, 1.08], [0.74, 1.7]]),
      S(-1.95, [[0.95, 0.24], [0.95, 1.1], [0.74, 1.7]]), S(-2.25, [[0.93, 0.28], [0.93, 1.06], [0.78, 1.4]]),
      S(-2.35, [[0.88, 0.36], [0.88, 0.98], [0.76, 1.1]])],
    glass: [2, 4], roof: 3, wheels: { x: [1.4, -1.42], r: 0.36 }, head: [0.66, 0.78, 0.45, 0.78], tail: [0.8, 0.96, 0.45, 0.8],
  },
  taxi: {
    stations: [S(2.28, [[0.8, 0.34], [0.8, 0.7], [0.68, 0.76]]), S(2.02, [[0.91, 0.22], [0.91, 0.88], [0.78, 0.94]]),
      S(0.95, [[0.91, 0.22], [0.91, 1.0], [0.8, 1.05]]), S(0.15, [[0.91, 0.22], [0.91, 1.02], [0.66, 1.6]]),
      S(-1.75, [[0.91, 0.22], [0.91, 1.04], [0.66, 1.6]]), S(-2.18, [[0.89, 0.26], [0.89, 1.0], [0.72, 1.32]]),
      S(-2.28, [[0.84, 0.34], [0.84, 0.92], [0.7, 1.02]])],
    glass: [2, 4], roof: 3, wheels: { x: [1.38, -1.38], r: 0.33 }, head: [0.58, 0.7, 0.42, 0.74], tail: [0.74, 0.88, 0.44, 0.76],
    extra: (b) => b.box(-0.55, -0.25, 1.59, 1.8, 0.42, SIGN),
  },
  // two-box hatchback (Clio 5, 208, C3): a rounded nose, short hood, the screen raked far forward, a sloped
  // tailgate over a short rear overhang; sections with a tumblehome (sill tucked in, shoulder, glass leaning
  // in), smooth-shaded (round: Builder.smooth)
  hatch: {
    stations: [S(2.05, [[0.66, 0.3], [0.74, 0.42], [0.74, 0.6], [0.6, 0.68]]),
      S(1.95, [[0.8, 0.22], [0.87, 0.42], [0.86, 0.74], [0.72, 0.8]]),
      S(1.6, [[0.84, 0.2], [0.9, 0.44], [0.89, 0.82], [0.77, 0.86]]),
      S(0.98, [[0.85, 0.2], [0.9, 0.46], [0.89, 0.9], [0.8, 0.93]]),
      S(0.02, [[0.85, 0.2], [0.9, 0.46], [0.89, 0.93], [0.64, 1.42]]),
      S(-1.2, [[0.85, 0.2], [0.9, 0.46], [0.89, 0.95], [0.64, 1.45]]),
      S(-1.78, [[0.84, 0.22], [0.89, 0.46], [0.87, 0.96], [0.68, 1.3]]),
      S(-1.98, [[0.8, 0.26], [0.86, 0.46], [0.83, 0.94], [0.68, 1.08]]),
      S(-2.05, [[0.72, 0.32], [0.8, 0.46], [0.78, 0.9], [0.64, 1.0]])],
    glass: [3, 5], roof: 4, round: true, wheels: { x: [1.3, -1.3], r: 0.31 }, head: [0.6, 0.72, 0.4, 0.68], tail: [0.74, 0.9, 0.46, 0.74],
  },
  // small crossover SUV (2008, Captur, T-Roc): higher, a black cladding band over the sills and arches, a
  // coupé-like sloped tailgate
  crossover: {
    stations: [S(2.175, [[0.74, 0.38], [0.82, 0.52], [0.82, 0.74], [0.68, 0.82]]),
      S(2.05, [[0.86, 0.28], [0.93, 0.52], [0.92, 0.9], [0.78, 0.96]]),
      S(1.55, [[0.88, 0.26], [0.95, 0.54], [0.94, 0.98], [0.82, 1.03]]),
      S(0.98, [[0.88, 0.26], [0.95, 0.55], [0.94, 1.03], [0.84, 1.07]]),
      S(-0.02, [[0.88, 0.26], [0.95, 0.55], [0.94, 1.07], [0.7, 1.56]]),
      S(-1.35, [[0.88, 0.26], [0.95, 0.55], [0.94, 1.09], [0.7, 1.58]]),
      S(-1.95, [[0.87, 0.28], [0.94, 0.55], [0.91, 1.1], [0.72, 1.36]]),
      S(-2.12, [[0.83, 0.32], [0.9, 0.55], [0.87, 1.06], [0.72, 1.16]]),
      S(-2.175, [[0.76, 0.38], [0.84, 0.55], [0.8, 1.0], [0.68, 1.08]])],
    glass: [3, 5], roof: 4, round: true, clad: true, wheels: { x: [1.36, -1.36], r: 0.36 }, head: [0.72, 0.84, 0.42, 0.72], tail: [0.82, 0.98, 0.46, 0.76],
  },
  // a Paris taxi (Prius, Corolla, Model 3): a dark saloon with the white "TAXI PARISIEN" light across the front
  // of the roof, its lamp green when free, red when taken
  taxi_paris: {
    stations: [S(2.375, [[0.8, 0.3], [0.8, 0.62], [0.66, 0.68]]), S(2.15, [[0.9, 0.18], [0.9, 0.78], [0.76, 0.84]]),
      S(0.95, [[0.91, 0.18], [0.91, 0.9], [0.8, 0.96]]), S(0.1, [[0.91, 0.18], [0.91, 0.94], [0.64, 1.36]]),
      S(-0.95, [[0.91, 0.18], [0.91, 0.95], [0.64, 1.36]]), S(-1.72, [[0.9, 0.18], [0.9, 0.96], [0.76, 1.02]]),
      S(-2.28, [[0.86, 0.22], [0.86, 0.94], [0.74, 0.99]]), S(-2.375, [[0.78, 0.32], [0.78, 0.84], [0.66, 0.88]])],
    glass: [2, 4], roof: 3, wheels: { x: [1.42, -1.38], r: 0.32 }, head: [0.5, 0.62, 0.42, 0.72], tail: [0.66, 0.8, 0.44, 0.74],
    extra: (b, kx, ky) => {
      const x = 0.1 * kx - 0.12, top = 1.36 * ky;
      b.box(x - 0.16, x, top - 0.02, top + 0.11, 0.25, SIGN_W);
      b.box(x - 0.13, x + 0.005, top + 0.03, top + 0.075, 0.07, LAMP);     // the lamp showing at the front
    },
  },
  // London's black cab (LEVC TX, 4.86 x 1.87 x 1.89 m): a rounded nose and a bonnet sloping down to it, a big
  // oval chrome grille, a raked windscreen, a tall cabin under a domed roof (sections: sill, shoulder, belt, the
  // cant rail, the crown: crown 1 strip of roof between the side glass and the flat top), an upright tailgate;
  // the "TAXI" sign (amber-lit when free) at the front of the roof
  taxi_london: {
    stations: [S(2.43, [[0.66, 0.34], [0.78, 0.46], [0.78, 0.66], [0.66, 0.76], [0.36, 0.79]]),
      S(2.33, [[0.84, 0.28], [0.91, 0.48], [0.9, 0.82], [0.8, 0.9], [0.44, 0.94]]),
      S(2.0, [[0.88, 0.26], [0.94, 0.5], [0.93, 0.97], [0.84, 1.03], [0.46, 1.07]]),
      S(1.5, [[0.88, 0.26], [0.94, 0.52], [0.93, 1.09], [0.86, 1.13], [0.46, 1.16]]),
      S(0.78, [[0.88, 0.26], [0.94, 0.52], [0.93, 1.14], [0.8, 1.74], [0.46, 1.86]]),
      S(-1.0, [[0.88, 0.26], [0.94, 0.52], [0.93, 1.16], [0.8, 1.76], [0.46, 1.888]]),
      S(-2.18, [[0.88, 0.27], [0.93, 0.52], [0.91, 1.14], [0.78, 1.72], [0.46, 1.84]]),
      S(-2.43, [[0.8, 0.34], [0.86, 0.52], [0.84, 1.06], [0.72, 1.6], [0.42, 1.68]])],
    glass: [3, 6], roof: 4, roofTo: 5, crown: 1, round: true, crease: 50, grille: false,
    wheels: { x: [1.5, -1.49], r: 0.33 }, head: [0.5, 0.66, 0.42, 0.7], tail: [0.8, 1.02, 0.62, 0.84],
    extra: (b, kx, ky, kz) => {
      b.box(0.5 * kx, 0.76 * kx, 1.85 * ky, 1.96 * ky, 0.22, SIGN);
      // the grille: a chrome surround, its dark mesh inset, between the headlamps
      const xf = 2.43 * kx;
      b.box(xf - 0.05, xf + 0.012, 0.4 * ky, 0.66 * ky, 0.38 * kz, CHROME);
      b.lights(xf + 0.016, 0.44 * ky, 0.62 * ky, 0.001, 0.32 * kz, TYRE);
    },
  },
  van: {
    stations: [S(2.52, [[0.86, 0.34], [0.86, 0.72], [0.74, 0.8]]), S(2.3, [[0.95, 0.24], [0.95, 0.92], [0.84, 0.98]]),
      S(1.8, [[0.95, 0.24], [0.95, 1.04], [0.86, 1.1]]), S(0.95, [[0.95, 0.24], [0.95, 1.1], [0.84, 1.98]]),
      S(-2.45, [[0.95, 0.24], [0.95, 1.1], [0.84, 1.98]]), S(-2.52, [[0.92, 0.28], [0.92, 1.06], [0.82, 1.9]])],
    glass: [2], roof: 3, wheels: { x: [1.75, -1.55], r: 0.33 }, head: [0.62, 0.76, 0.45, 0.8], tail: [0.9, 1.3, 0.72, 0.86],
  },
};

function carModel(def, dims) {
  const b = new Builder();
  const L0 = def.stations[0].x - def.stations[def.stations.length - 1].x;
  const H0 = Math.max(...def.stations.flatMap((s) => s.pts.map((p) => p[1])));
  const W0 = 2 * Math.max(...def.stations.flatMap((s) => s.pts.map((p) => p[0])));
  const kx = dims.length / L0, ky = dims.height / H0, kz = dims.width / W0;
  const st = def.stations.map((s) => ({ x: s.x * kx, pts: s.pts.map(([w, y]) => [w * kz, y * ky]) }));
  // (roof: the station gap of the roof, or roof..roofTo; crown: strips of rounded roof between the side glass
  // and the top strip, glass over the windscreen and rear window like the top)
  const isRoof = (i) => i >= def.roof && i <= (def.roofTo ?? def.roof);
  const cabin = (i) => def.glass.includes(i) || isRoof(i);
  const m = def.stations[0].pts.length - 1;            // top strip m, greenhouse g, body below
  const g = m - 1 - (def.crown ?? 0);
  b.loft(st, (i, j) => {
    if (j > g) return def.glass.includes(i) ? GLASS : isRoof(i) ? PAINT2 : PAINT;
    if (j === g) return cabin(i) ? GLASS : PAINT;
    return def.clad && j === 0 ? TYRE : PAINT;          // (a crossover's black cladding over the sills)
  }, (end, j) => (def.clad && j === 0 ? TYRE : PAINT), 0.45 * dims.height);
  const wOut = Math.max(...st.map((s) => s.pts[m > 2 ? 1 : 0][0])) + (def.round ? -0.02 : 0.025);
  for (const x of def.wheels.x) b.wheels(x * kx, def.wheels.r, wOut);
  const xf = st[0].x + 0.01, xr = st[st.length - 1].x - 0.01;
  b.lights(xf, def.head[0] * ky, def.head[1] * ky, def.head[2] * kz, def.head[3] * kz, HEAD);
  b.lights(xr, def.tail[0] * ky, def.tail[1] * ky, def.tail[2] * kz, def.tail[3] * kz, TAIL);
  // bumpers: a dark band wrapping each end a little proud of the body; a grille between the headlamps;
  // mirrors at the windscreen's foot
  const endW = (S_) => Math.max(...S_.pts.slice(0, m).map((q) => q[0]));
  const wf = endW(st[0]), wr = endW(st[st.length - 1]);
  b.box(xf - 0.02, xf + 0.06, 0.2 * ky, 0.42 * ky, wf + 0.03, TRIM);
  b.box(xr - 0.06, xr + 0.02, 0.22 * ky, 0.44 * ky, wr + 0.03, TRIM);
  if (def.grille !== false) b.lights(xf + 0.005, def.head[0] * ky, def.head[1] * ky * 0.98, 0.02, def.head[2] * kz - 0.02, TYRE);
  const gi = Math.min(def.glass[0], st.length - 2), xm = st[gi].x - 0.05, ym = st[gi].pts[g][1] + 0.08;
  const wm = st[gi].pts[g][0];
  for (const sgn of [1, -1]) {
    const z0 = sgn * wm, z1 = sgn * (wm + 0.2);
    b.quad([xm, ym, z0], [xm, ym, z1], [xm, ym + 0.14, z1], [xm, ym + 0.14, z0], PAINT, [xm - 1, ym, 0]);
    b.quad([xm - 0.12, ym, z0], [xm - 0.12, ym, z1], [xm - 0.12, ym + 0.14, z1], [xm - 0.12, ym + 0.14, z0], PAINT, [xm + 1, ym, 0]);
    b.quad([xm, ym + 0.14, z0], [xm, ym + 0.14, z1], [xm - 0.12, ym + 0.14, z1], [xm - 0.12, ym + 0.14, z0], PAINT, [xm, ym, 0]);
    b.quad([xm, ym, z1], [xm - 0.12, ym, z1], [xm - 0.12, ym + 0.14, z1], [xm, ym + 0.14, z1], PAINT, [xm, ym, 0]);
  }
  def.extra?.(b, kx, ky, kz);
  if (def.round) b.smooth(def.crease);
  return b.geometry();
}

// city.json cars.posts (default off): window posts in the body colour across the glazing bands of the buses and the
// double-decker, every ~1.4 m (Berlin M6 critic: the BVG buses read as navy boxes, one dark band end to end); the
// trams always have theirs
let POSTS = false;
function posts(b, x0, x1, y0, y1, w, pitch = 1.4, part = PAINT) {
  const n = Math.max(1, Math.round((x1 - x0) / pitch));
  for (let i = 0; i <= n; i++) {
    const c = x0 + ((x1 - x0) * i) / n;
    b.box(c - 0.07, c + 0.07, y0, y1, w + 0.015, part);
  }
}

// idfm: Île-de-France Mobilités' livery (2017-): a silver-grey body (vif-argent) round a full-length dark
// glazing band (sides, windscreen, rear window), blue-turquoise accents (the second colour: a stripe along the
// skirt, the lower rear), the route panel over the windscreen, the roof and its pods silver
function busModel(d, idfm = false) {
  const b = new Builder(), x = d.length / 2, w = d.width / 2, h = d.height;
  const sec = (ww, top) => [[ww, 0.32], [ww, 1.05], [ww, 2.72], [ww - 0.07, top]];
  const side = idfm ? (i, j) => (j === 1 ? GLASS : PAINT)
    : (i, j) => (j === 0 ? PAINT : j === 1 ? GLASS : PAINT2);
  const cap = idfm ? (end, j) => (j === 1 ? GLASS : end === 0 && j === 2 ? SIGN : end === 1 && j === 0 ? PAINT2 : PAINT)
    : (end, j) => (j === 0 ? PAINT : j === 1 ? GLASS : PAINT2);
  if (idfm) {
    b.box(-x + 0.3, x - 0.3, 0.4, 0.55, w + 0.012, PAINT2);                     // the accent stripe on the skirt
    b.box(-x + 0.05, -x + 2.2, 0.55, 0.98, w + 0.01, PAINT2);                  // ... sweeping up at the rear
  }
  b.loft([S(x, sec(w - 0.07, h - 0.14)), S(x - 0.18, sec(w, h)), S(-x + 0.15, sec(w, h)), S(-x, sec(w - 0.06, h - 0.12))],
    side, cap, h * 0.45);
  b.box(-x + 1.6, x - 2.8, h - 0.02, h + 0.3, w - 0.35, idfm ? PAINT : PAINT2);   // batteries and air conditioning
  if (POSTS && !idfm) posts(b, -x + 0.6, x - 1.2, 1.05, 2.72, w);
  b.wheels(x - 2.6, 0.5, w + 0.02, 0.3);
  b.wheels(-x + 3.1, 0.5, w + 0.02, 0.3);
  b.lights(x + 0.01, 0.55, 0.8, w - 0.45, w - 0.12, HEAD);
  b.lights(-x - 0.01, 0.6, 1.0, w - 0.4, w - 0.12, TAIL);
  return b.geometry();
}

// London's double-deck bus (New Routemaster, Enviro400; 11.2 x 2.55 x 4.4 m): TfL red all over, a dark band of
// glass on each deck, the destination blind over the windscreen between the decks, a dark grey skirt (the
// second colour)
function busDDModel(d) {
  const b = new Builder(), x = d.length / 2, w = d.width / 2, h = d.height, k = h / 4.4;
  const sec = (ww, top) => [[ww, 0.3 * k], [ww, 1.12 * k], [ww, 2.22 * k], [ww, 2.62 * k], [ww, 3.86 * k], [ww - 0.1, top]];
  const side = (i, j) => (j === 1 || j === 3 ? GLASS : PAINT);
  const cap = (end, j) => (j === 3 || (j === 1 && end === 0) ? GLASS : end === 0 && j === 2 ? SIGN : PAINT);
  b.loft([S(x, sec(w - 0.12, h - 0.16)), S(x - 0.3, sec(w, h)), S(-x + 0.25, sec(w, h)), S(-x, sec(w - 0.1, h - 0.12))],
    side, cap, h * 0.45);
  b.box(-x + 0.1, x - 0.1, 0.3, 0.52, w + 0.012, PAINT2);                     // the skirt
  if (POSTS) { posts(b, -x + 0.5, x - 1.0, 1.12 * k, 2.22 * k, w); posts(b, -x + 0.5, x - 0.5, 2.62 * k, 3.86 * k, w); }
  b.wheels(x - 2.4, 0.5, w + 0.02, 0.3);
  b.wheels(-x + 2.9, 0.5, w + 0.02, 0.3);
  b.lights(x + 0.01, 0.5, 0.72, w - 0.45, w - 0.12, HEAD);
  b.lights(-x - 0.01, 0.55, 0.95, w - 0.4, w - 0.12, TAIL);
  return b.geometry();
}

// an articulated bus (Berlin's MAN Lion's City G, 18 m): busModel's body with a dark bellows band at the joint
// (0.42 of the length from the front) and a third axle
function busArtModel(d) {
  const g = new Builder(), x = d.length / 2, w = d.width / 2, h = d.height;
  const sec = (ww, top) => [[ww, 0.32], [ww, 1.05], [ww, 2.72], [ww - 0.07, top]];
  const side = (i, j) => (j === 0 ? PAINT : j === 1 ? GLASS : PAINT2);
  const cap = (end, j) => (j === 0 ? PAINT : j === 1 ? GLASS : PAINT2);
  const xj = x - 0.42 * d.length;                    // the joint
  g.loft([S(x, sec(w - 0.07, h - 0.14)), S(x - 0.18, sec(w, h)), S(xj + 0.45, sec(w, h))], side, cap, h * 0.45);
  g.loft([S(xj - 0.45, sec(w, h)), S(-x + 0.15, sec(w, h)), S(-x, sec(w - 0.06, h - 0.12))], side, cap, h * 0.45);
  g.box(xj - 0.46, xj + 0.46, 0.4, h - 0.12, w - 0.1, TYRE);                // the bellows
  g.box(xj + 1.2, x - 2.8, h - 0.02, h + 0.28, w - 0.35, PAINT2);            // roof pods
  if (POSTS) { posts(g, xj + 0.6, x - 1.2, 1.05, 2.72, w); posts(g, -x + 0.6, xj - 0.6, 1.05, 2.72, w); }
  g.wheels(x - 2.6, 0.5, w + 0.02, 0.3);
  g.wheels(xj - 0.9, 0.5, w + 0.02, 0.3);
  g.wheels(-x + 2.1, 0.5, w + 0.02, 0.3);
  g.lights(x + 0.01, 0.55, 0.8, w - 0.45, w - 0.12, HEAD);
  g.lights(-x - 0.01, 0.6, 1.0, w - 0.4, w - 0.12, TAIL);
  return g.geometry();
}

// a tram module (Berlin's Flexity: BVG yellow, a black window band, a pale roof, a dark skirt over the bogies),
// one car of an articulated train (06d_cars [cars.trams]: the modules follow each other along the track, so the
// train bends at its joints). kind: 'cab' (the front: a raked windscreen under the destination display, head
// lamps), 'tail' (the same cab facing back, tail lamps), 'mid' (a plain module, dark bellows at both ends and a
// pantograph)
function tramModel(d, kind) {
  const b = new Builder(), x = d.length / 2, w = d.width / 2, h = d.height, k = h / 3.4;
  // (M6 fix round: the glass band 1.02-2.3 m, 38 % of the height, a yellow band over it and the white roof's
  // shoulder, yellow posts between the windows: the dark band end to end read navy)
  const sec = (ww, top, lo = 0.36) => [[ww, lo * k], [ww, 1.02 * k], [ww, 2.3 * k], [ww, 2.78 * k], [ww - 0.16, top]];
  const side = (i, j) => (j === 1 ? GLASS : j === 3 ? PAINT2 : PAINT);
  if (kind === 'mid') {
    b.loft([S(x - 0.15, sec(w, h)), S(-x + 0.15, sec(w, h))], side, (end, j) => TYRE, h * 0.45);
    b.box(-x - 0.13, x + 0.13, 0.6 * k, h - 0.25, w - 0.15, TYRE);             // bellows (end to end, hidden mid-body)
    b.beam([-0.9, h + 0.05], [0.25, h + 0.75], 0, 0.45, 0.04, TRIM);            // pantograph
    b.beam([0.25, h + 0.75], [-0.4, h + 1.2], 0, 0.55, 0.035, TRIM);
    b.box(-0.6, 0.6, h - 0.02, h + 0.2, w - 0.5, PAINT2);
  } else {
    const dir = kind === 'tail' ? -1 : 1, X = (v) => v * dir;
    // the nose: the screen raked back from the dash, its top under the display
    const nose = [[w - 0.5, 0.36 * k], [w - 0.3, 1.02 * k], [w - 0.42, 2.3 * k], [w - 0.5, 2.78 * k], [w - 0.62, h - 0.2]];
    b.loft([S(X(x), nose), S(X(x - 0.55), sec(w - 0.08, h - 0.08)), S(X(x - 1.1), sec(w, h)), S(X(-x + 0.15), sec(w, h))],
      side, (end, j) => (end === 0 ? (j === 1 ? GLASS : j === 2 ? SIGN : j === 0 ? PAINT2 : PAINT) : TYRE), h * 0.45);
    b.lights(X(x + 0.012), 0.55 * k, 0.75 * k, w - 0.95, w - 0.6, dir > 0 ? HEAD : TAIL);
    b.box(X(-x + 0.6), X(x - 1.6), h - 0.02, h + 0.24, w - 0.45, PAINT2);      // the roof's equipment
    b.box(X(-x - 0.13), X(-x + 0.3), 0.6 * k, h - 0.25, w - 0.15, TYRE);       // the bellows to the next module
  }
  b.box(-x + 0.2, x - 0.2, 0.1, 0.38 * k, w - 0.02, TYRE);                    // skirt over the bogies
  if (kind === 'mid') posts(b, -x + 0.4, x - 0.4, 1.02 * k, 2.3 * k, w, 1.3);
  else posts(b, kind === 'tail' ? -x + 1.3 : -x + 0.4, kind === 'tail' ? x - 0.4 : x - 1.3, 1.02 * k, 2.3 * k, w, 1.3);
  return b.geometry();
}

function truckModel(d) {
  const b = new Builder(), x = d.length / 2, w = d.width / 2, h = d.height;
  const cab = (ww, top) => [[ww, 0.5], [ww, 1.35], [ww - 0.02, 2.3], [ww - 0.08, top]];
  b.loft([S(x, cab(w - 0.1, 2.45)), S(x - 0.1, cab(w - 0.03, 2.55)), S(x - 1.7, cab(w - 0.03, 2.55))],
    (i, j) => (j === 1 ? GLASS : PAINT), (end, j) => (end === 0 && j === 1 ? GLASS : PAINT), 1.4);
  b.box(-x, x - 1.8, 0.95, h, w, PAINT2);                               // the cargo box
  b.box(-x + 0.2, x - 0.4, 0.45, 0.98, w * 0.42, TRIM);                  // chassis
  b.wheels(x - 1.05, 0.45, w - 0.02, 0.28);
  b.wheels(-x + 1.6, 0.45, w - 0.02, 0.4);
  b.lights(x + 0.01, 0.6, 0.8, w - 0.4, w - 0.1, HEAD);
  b.lights(-x - 0.01, 1.0, 1.2, w - 0.3, w - 0.08, TAIL);
  return b.geometry();
}

function lorryModel(d) {
  const b = new Builder(), x = d.length / 2, w = d.width / 2, h = d.height;
  const cab = (ww, top) => [[ww, 0.6], [ww, 1.5], [ww - 0.02, 2.55], [ww - 0.1, top]];
  b.loft([S(x, cab(w - 0.1, 2.95)), S(x - 0.12, cab(w - 0.03, 3.05)), S(x - 2.1, cab(w - 0.03, 3.05))],
    (i, j) => (j === 1 ? GLASS : PAINT), (end, j) => (end === 0 && j === 1 ? GLASS : PAINT), 1.6);
  // roof fairing up to the container's height
  b.loft([S(x - 0.5, [[w - 0.2, 3.02], [w - 0.35, 3.5]]), S(x - 2.1, [[w - 0.13, 3.02], [w - 0.3, h - 0.2]])],
    () => PAINT, () => PAINT, 3.2);
  b.box(-x + 0.1, x - 2.0, 0.55, 1.3, w * 0.45, TRIM);                  // chassis and trailer frame
  b.box(-x, x - 2.3, 1.32, h - 0.05, w - 0.02, PAINT2);                 // the container
  b.wheels(x - 1.25, 0.52, w - 0.02, 0.3);
  for (const wx of [x - 4.2, x - 5.5, -x + 3.7, -x + 2.4, -x + 1.1]) b.wheels(wx, 0.52, w - 0.02, 0.45);
  b.lights(x + 0.01, 0.7, 0.95, w - 0.4, w - 0.1, HEAD);
  b.lights(-x - 0.01, 0.9, 1.15, w - 0.35, w - 0.08, TAIL);
  return b.geometry();
}

// a scooter or motorbike (built to its own size, about 2 m) and its rider: a bench body with a leg shield, a
// seat, the bars; the rider sitting upright, hands on the bars, a helmet
function motoModel(d) {
  const b = new Builder(), x = d.length / 2;
  const r = 0.3;
  b.wheel1(x - 0.33, r, 0.06);
  b.wheel1(-x + 0.36, r, 0.07);
  b.box(-0.6, 0.42, 0.28, 0.52, 0.2, PAINT);              // floor board and frame
  b.box(0.42, 0.62, 0.3, 1.0, 0.23, PAINT);               // leg shield and steering column
  b.beam([x - 0.33, r], [0.6, 1.02], 0, 0.04, 0.035, TRIM);   // front fork
  b.box(-x + 0.08, -0.1, 0.42, 0.8, 0.19, PAINT);         // the body under the seat
  b.box(-0.78, 0.02, 0.8, 0.9, 0.16, TYRE);               // seat
  b.box(0.5, 0.6, 1.0, 1.06, 0.36, TYRE);                 // handlebar
  b.lights(0.625, 0.78, 0.92, 0.0, 0.09, HEAD);
  b.lights(-x + 0.075, 0.6, 0.7, 0.0, 0.08, TAIL);
  // rider
  b.box(-0.55, 0.05, 0.84, 1.0, 0.17, RIDER);             // thighs on the seat
  for (const z of [0.12, -0.12]) b.beam([0.08, 0.95], [0.3, 0.4], z, 0.06, 0.07, RIDER);   // shins to the board
  b.beam([-0.42, 0.98], [-0.28, 1.5], 0, 0.19, 0.13, RIDER);                              // torso, leaning in
  for (const z of [0.2, -0.2]) b.beam([-0.26, 1.44], [0.52, 1.07], z, 0.05, 0.05, RIDER);  // arms to the bars
  b.box(-0.4, -0.12, 1.52, 1.8, 0.13, HELMET);
  return b.geometry();
}

// far box (x -0.5..0.5 along, y 0..1, z -0.5..0.5), no bottom
function unitBox() {
  const b = new Builder();
  b.loft([S(0.5, [[0.5, 0], [0.5, 1]]), S(-0.5, [[0.5, 0], [0.5, 1]])], () => 0, () => 0, 0.5);
  return b.geometry();
}

// shadow proxy: a convex hull through the footprint (level 0), the shoulder (1) and the roof (2), as
// corner codes (sign along, level, sign across); the shader places them per type and projects them
function shadowHull() {
  const pos = [], code = [];
  // reference placement just to wind every face outwards
  const place = ([sx, lv, sz]) => [lv === 2 ? sx * 0.3 : sx * 0.5, [0, 0.55, 1][lv], sz * (lv === 2 ? 0.4 : 0.5)];
  const faces = [];
  const ring = (lv) => [[1, lv, 1], [1, lv, -1], [-1, lv, -1], [-1, lv, 1]];
  for (let lv = 0; lv < 2; lv++) {
    const a = ring(lv), c = ring(lv + 1);
    for (let k = 0; k < 4; k++) faces.push([a[k], a[(k + 1) % 4], c[(k + 1) % 4], c[k]]);
  }
  faces.push(ring(2));
  for (const f of faces) {
    const P = f.map(place);
    for (const [i, j, k] of [[0, 1, 2], [0, 2, 3]]) {
      const u = P[j].map((v, q) => v - P[i][q]), v = P[k].map((vv, q) => vv - P[i][q]);
      const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
      const m = [0, 1, 2].map((q) => (P[i][q] + P[j][q] + P[k][q]) / 3 - [0, 0.5, 0][q]);
      const tri = n[0] * m[0] + n[1] * m[1] + n[2] * m[2] < 0 ? [f[i], f[k], f[j]] : [f[i], f[j], f[k]];
      for (const c of tri) { code.push(...c); pos.push(0, 0, 0); }
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('corner', new THREE.Float32BufferAttribute(code, 3));
  return g;
}

// ---------------------------------------------------------------- materials
const U = {
  camPos: uniform(new THREE.Vector3()), sunDir: uniform(new THREE.Vector3(0, 1, 0)), sunUp: uniform(1),
  // glass: how much of the sky it reflects (0.45: dark from above) and a lift of its tint; city.json
  // cars.glass {reflect, tint} (Paris: 0.95, 1.25: the windows show the sky, cars read less like flat boxes)
  glassK: uniform(0.45), glassTint: uniform(1),
  // (city.json cars.glass.transit: the buses' and trams' (the silver-flag types') glass reflects this share of the
  // cars' and takes no tint lift: near-black bands, not the sky's navy; 1 by default)
  transitK: uniform(1),
  lorryT: uniform(6),          // the lorry type's index (container corrugation on its second colour)
};
const poseAttr = attribute('pose', 'vec4');      // x, y, z, heading + 8 x fade level (0..15)
const lookAttr = attribute('look', 'vec4');      // packed sRGB body colour, second colour, type, seed (+ 1: parked)
const fadeLevel = floor(poseAttr.w.add(4).div(8));
const heading = poseAttr.w.sub(fadeLevel.mul(8));
const carFade = varying(fadeLevel.div(15));
const hc = cos(heading), hs = sin(heading);
const rotY = (v) => vec3(v.x.mul(hc).sub(v.z.mul(hs)), v.y, v.x.mul(hs).add(v.z.mul(hc)));
const unpack = (packed) => {                     // 24-bit sRGB -> linear
  const p = packed.add(0.5);
  const r = floor(p.div(65536)), g = floor(p.div(256)).sub(r.mul(256)), b = floor(p).sub(floor(p.div(256)).mul(256));
  return pow(vec3(r, g, b).div(255), vec3(2.2));
};
const colA = varying(unpack(lookAttr.x)), colB = varying(unpack(lookAttr.y));
const typeF = lookAttr.z;
const driving = select(lookAttr.w.lessThan(1), float(1), float(0));   // lights on (parked cars' seeds are 1 + seed)
const HEAD_ON = vec3(1, 0.9, 0.75), TAIL_ON = vec3(1, 0.02, 0.01), BUS_LIT = vec3(1, 0.88, 0.66);    // lit lamps (linear, times their strength)
const dither = fract(float(52.9829189).mul(fract(dot(screenCoordinate.xy, vec2(0.06711056, 0.00583715)))));
const DARK_GLASS = vec3(0.018, 0.022, 0.028), TYRE_C = vec3(0.025, 0.025, 0.027), TRIM_C = vec3(0.3, 0.3, 0.3);
const HEAD_C = vec3(0.85, 0.85, 0.8), TAIL_C = vec3(0.45, 0.02, 0.02), SIGN_C = vec3(0.85, 0.8, 0.45);
const RIDER_C = vec3(0.03, 0.03, 0.035), SIGN_W_C = vec3(0.78, 0.78, 0.76), LAMP_C = vec3(0.05, 0.05, 0.05);
const CHROME_C = vec3(0.5, 0.51, 0.52);

// sky and ground reflected in paint (clear coat) and glass: Schlick Fresnel, the sky above the horizon and
// a dark city below it, as the facades' glass does
function reflection(env, f0, roughness) {
  const ndv = normalView.dot(positionViewDirection).saturate();
  const fresnel = f0.add(float(1).sub(f0).mul(pow(float(1).sub(ndv), 5)));
  const r = reflectVector.normalize();
  const sky = pmremTexture(env, r, roughness).rgb;
  const horizon = pmremTexture(env, vec3(r.x, float(0.03), r.z), float(0.3)).rgb.mul(vec3(0.3, 0.29, 0.28));
  const seen = mix(sky, horizon, smoothstep(float(0.08), float(-0.05), r.y));
  // the sky map is HDR (several units near the horizon): added as it is, even 5 % of it washed every car
  // white and taxis lost their yellow. A soft shoulder and the coat's own dimming, as the facades' glass has
  return seen.div(seen.mul(0.8).add(1)).mul(0.5).mul(fresnel);
}

function shade(m, env, part, lp, lw, transit = float(0)) {
  const P = floor(part.add(0.5));
  const lt = (k) => P.lessThan(k + 0.5);
  // container corrugation on lorries (fades before it could shimmer)
  const dist = positionWorld.distance(U.camPos);
  const corr = select(typeF.sub(U.lorryT).abs().lessThan(0.5).and(P.equal(PAINT2)),
    sin(lp.x.mul(Math.PI * 2 / 0.3)).mul(0.07).mul(float(1).sub(smoothstep(float(60), float(160), dist))), float(0));
  const seedTone = fract(lookAttr.w).mul(0.08).add(0.96);                  // cars aren't all freshly washed
  const paint = select(lt(PAINT), colA, colB).mul(seedTone).mul(corr.add(1));
  const albedo = select(lt(PAINT2), paint, select(lt(GLASS), DARK_GLASS.mul(mix(U.glassTint, float(1), transit)), select(lt(TYRE), TYRE_C,
    select(lt(HEAD), HEAD_C, select(lt(TAIL), TAIL_C, select(lt(TRIM), TRIM_C, select(lt(SIGN), SIGN_C,
      select(lt(RIDER), RIDER_C, select(lt(HELMET), colB, select(lt(SIGN_W), SIGN_W_C, select(lt(LAMP), LAMP_C, CHROME_C)))))))))));
  // underbody and sills in shadow, darker near the ground
  const under = smoothstep(float(0.05), float(0.6), lw.y).mul(0.45).add(0.55);
  m.colorNode = albedo.mul(select(lt(PAINT2), under, float(1)));
  m.roughnessNode = select(lt(PAINT2), float(0.42), select(lt(GLASS), float(0.08), select(lt(TYRE), float(0.9), float(0.5))));
  m.metalnessNode = float(0);
  const f0 = select(lt(PAINT2), float(0.045), select(lt(GLASS), float(0.07), select(P.equal(CHROME), float(0.5), float(0))));
  const rough = select(lt(PAINT2), float(0.12), float(0.04));
  // tinted glass: the sky it reflects comes back dimmed, so windows read dark from above, as in photos
  const reflK = select(lt(PAINT2).or(P.equal(CHROME)), float(1), U.glassK.mul(mix(float(1), U.transitK, transit)));
  // (a taxi's roof lamp: green when free, red when taken, by the car's seed; lit on moving taxis only)
  const lamp = select(fract(lookAttr.w.mul(7.13)).lessThan(0.4), vec3(0.05, 0.9, 0.25), vec3(0.95, 0.06, 0.04)).mul(driving).mul(0.8);
  m.emissiveNode = reflection(env, f0, rough).mul(reflK).add(select(P.equal(TAIL), vec3(0.03, 0.001, 0.001),
    select(P.equal(LAMP), lamp, vec3(0))));   // the lenses' own red by day, unlit
  const farFade = float(1).sub(smoothstep(float(FAR - FAR_FADE), float(FAR), dist));
  // (no rider on a parked two-wheeler)
  const riderOff = P.greaterThan(RIDER - 0.5).and(P.lessThan(HELMET + 0.5)).and(driving.lessThan(0.5));
  m.maskNode = dither.lessThan(carFade.mul(farFade)).and(riderOff.not());
}

function nearMaterial(env, night, info = []) {
  const m = new THREE.MeshStandardNodeMaterial();
  const lp = attribute('position', 'vec3'), ln = attribute('normal', 'vec3');
  m.positionNode = rotY(lp).add(poseAttr.xyz);
  m.normalNode = transformNormalToView(varying(rotY(ln)));
  const part = varying(attribute('part', 'float'));
  let transit = float(0);
  for (let i = 0; i < info.length; i++) if (info[i].silver || info[i].transit) transit = transit.add(select(int(typeF.add(0.5)).equal(i), float(1), float(0)));
  shade(m, env, part, varying(lp), varying(lp), transit);
  // lit lamps, in the material's lit copy (night.js)
  const P = floor(part.add(0.5));
  // (night.busLights: buses' saloons lit, their glass glowing warm white; the bus types are those with a silver flag)
  let bus = float(0);
  if (night?.busLights) for (let i = 0; i < info.length; i++) if (info[i].silver) bus = bus.add(select(int(typeF.add(0.5)).equal(i), float(1), float(0)));
  if (night) night.withLights(m, select(P.equal(HEAD), HEAD_ON.mul(5), select(P.equal(TAIL), TAIL_ON.mul(3),
    select(P.equal(GLASS), BUS_LIT.mul(bus).mul(night.busLights ?? 0), vec3(0)))).mul(driving));
  return m;
}

// per type: (length, width, height, shoulder as a share of the height) and for the box and the shadow
// (hood end, roof front, roof rear, boot start as shares of the length from -0.5 to 0.5), (cargo from, window top, roof width, 0)
function farMaterial(env, info, night) {
  const dims = uniformArray(info.map((t) => new THREE.Vector4(t.length, t.width, t.height, t.belt)), 'vec4');
  const cab = uniformArray(info.map((t) => new THREE.Vector4(...t.cab)), 'vec4');
  const box = uniformArray(info.map((t) => new THREE.Vector4(t.cargo, t.winTop, t.roofW, t.silver ?? 0)), 'vec4');
  const ti = int(typeF.add(0.5));
  const D = dims.element(ti), C = cab.element(ti), B = box.element(ti);
  const m = new THREE.MeshStandardNodeMaterial();
  const u = attribute('position', 'vec3'), un = attribute('normal', 'vec3');
  const lp = vec3(u.x.mul(D.x), u.y.mul(D.z), u.z.mul(D.y));
  m.positionNode = rotY(lp).add(poseAttr.xyz);
  m.normalNode = transformNormalToView(varying(rotY(un)));
  const vu = varying(u), vn = varying(un);
  // parts from the position on the box: top (hood, windscreen, roof, rear window, boot), sides (tyres,
  // body, window band), cargo (the second colour)
  const x = vu.x, y = vu.y;
  const top = vn.y.greaterThan(0.5);
  const topPart = select(x.greaterThan(C.x), float(PAINT), select(x.greaterThan(C.y), float(GLASS),
    select(x.greaterThan(C.z), float(PAINT2), select(x.greaterThan(C.w), float(GLASS), float(PAINT)))));
  const deck = B.w.greaterThan(1.5).and(y.greaterThan(0.505)).and(y.lessThan(0.595));   // between a double-decker's decks
  const sidePart = select(y.lessThan(0.12), float(TYRE), select(y.lessThan(D.w), float(PAINT),
    select(y.lessThan(B.y).and(x.lessThan(C.x)).and(x.greaterThan(C.w)).and(deck.not()), float(GLASS), float(PAINT2))));
  const part0 = select(x.lessThan(B.x).and(y.greaterThan(0.2)), float(PAINT2), select(top, topPart, sidePart));
  // (a body in one colour above the windows: the IDFM bus's silver roof, not its blue accents)
  const part = select(B.w.greaterThan(0.5).and(part0.equal(PAINT2)), float(PAINT), part0);
  shade(m, env, part, lp, lp, uniformArray(info.map((t) => (t.silver || t.transit ? 1 : 0)), 'float').element(ti));
  // lit lamps (the material's lit copy): the whole lower front and rear faces, brighter than the models' (a
  // box a pixel or two across must still show them), and faintly the ends of the roof
  if (night) {
    let lit = select(vn.x.greaterThan(0.5), HEAD_ON.mul(8), select(vn.x.lessThan(-0.5), TAIL_ON.mul(6),
      select(top.and(x.greaterThan(0.35)), HEAD_ON.mul(1.2), select(top.and(x.lessThan(-0.4)), TAIL_ON.mul(1.2), vec3(0)))))
      .mul(select(top, float(1), select(y.lessThan(D.w), float(1), float(0.25))));
    // (night.carSpots: a box's end lit as its two lamps, once the car is a few pixels wide; under that its whole end
    // at the lamps' mean, so a far car stays a point. Lit whole ends read as big red squares from a few hundred
    // metres: Paris M8)
    if (night.carSpots) {
      const end = vn.x.abs().greaterThan(0.5);
      const widthPx = float(1).div(max(fwidth(vu.z), 1e-4));               // the box is 1 wide in u.z
      const spot = smoothstep(float(0.26), float(0.34), abs(vu.z)).mul(smoothstep(float(0.3), float(0.36), y))
        .mul(float(1).sub(smoothstep(float(0.5), float(0.56), y)));
      const near = smoothstep(float(3), float(8), widthPx);
      lit = lit.mul(select(end, mix(float(0.35), spot.mul(1.6), near), float(1)));
    }
    if (night.busLights) lit = lit.add(select(B.w.greaterThan(0.5).and(part.equal(GLASS)).and(top.not()), BUS_LIT.mul(night.busLights), vec3(0)));
    night.withLights(m, lit.mul(driving));
  }
  return { m, dims, cab, box };
}

// sunShade (city.json cars.sunShade, off by default): the proxy looks the sun's shadow map up where it lands and
// leaves out what already lies in a building's or a tree's shadow (drawn over it, it doubled the shade into a
// dark blob beside the car)
// shadowFade (city.json cars.shadowFade, 0 by default): the shadow lightens towards its far end, by that share where
// the roof's corners land (a penumbra that widens with the distance from the car). London M9 round 2: under a low sun
// behind the camera each car's shadow runs a car's length up the street, and drawn evenly dark it read as a dark
// translucent box behind every car; London 0.5
function shadowMaterial(uniforms, sunLight = null, shadowFade = 0) {
  const { dims, cab, box } = uniforms;
  const ti = int(typeF.add(0.5));
  const D = dims.element(ti), C = cab.element(ti), B = box.element(ti);
  const m = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false });
  const c = attribute('corner', 'vec3');
  const lv = c.y;
  // roof corners: from the rear of the rear window to the front of the windscreen, a little narrower
  const ux = select(lv.greaterThan(1.5), select(c.x.greaterThan(0), C.y.add(C.x).mul(0.5), C.z.add(C.w).mul(0.5)), c.x.mul(0.5));
  const uy = select(lv.greaterThan(1.5), float(1), select(lv.greaterThan(0.5), D.w, float(0)));
  const uz = c.z.mul(0.5).mul(select(lv.greaterThan(1.5), B.z, float(1)));
  const lp = vec3(ux.mul(D.x), uy.mul(D.z), uz.mul(D.y));
  const w = rotY(lp).add(poseAttr.xyz);
  const s = U.sunDir;
  const k = lp.y.div(max(s.y, 0.08));
  m.positionNode = vec3(w.x.sub(s.x.mul(k)), poseAttr.y.add(0.1), w.z.sub(s.z.mul(k)));
  const dist = positionWorld.distance(U.camPos);
  m.colorNode = vec3(0.0, 0.004, 0.012);
  const far = shadowFade ? float(1).sub(varying(lp.y.div(max(D.z, 0.1))).mul(shadowFade)) : float(1);
  let op = float(0.5).mul(far).mul(U.sunUp).mul(carFade).mul(float(1).sub(smoothstep(float(SHADOW * 0.75), float(SHADOW), dist)));
  if (sunLight?.shadow) op = op.mul(shadow(sunLight, sunLight.shadow).r);
  m.opacityNode = op;
  m.side = THREE.FrontSide;
  return m;
}

// ---------------------------------------------------------------- tile decoding
async function gunzip(buf) {
  const b = new Uint8Array(buf);
  if (b[0] !== 0x1f || b[1] !== 0x8b) return buf;
  return new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
}
// sRGB colours as 24-bit numbers (THREE.Color would convert them to linear): parse by hand
const packHex = (h) => parseInt(h.slice(1), 16);

function decodeTile(buf, t, palettes) {
  const u8 = new Uint8Array(buf), dv = new DataView(buf);
  const nl = dv.getUint32(0, true), np = dv.getUint32(4, true), nm = dv.getUint32(8, true), nq = dv.getUint32(12, true);
  let off = 16;
  const u16 = (n) => { const a = new Uint16Array(n); for (let i = 0; i < n; i++) a[i] = u8[off + i] | (u8[off + n + i] << 8); off += 2 * n; return a; };
  const i16sum = (n, base) => {
    const a = new Float32Array(n); let q = 0;
    for (let i = 0; i < n; i++) { let d = u8[off + i] | (u8[off + n + i] << 8); if (d > 32767) d -= 65536; q += d; a[i] = base + q / 10; }
    off += 2 * n; return a;
  };
  const bytes = (n) => { const a = u8.slice(off, off + n); off += n; return a; };
  const hPts = u16(nl), hCars = u16(nl), hSpeed = u16(nl), hD = u16(nl), hStop = u16(nl);
  const px = i16sum(np, t.x), pz = i16sum(np, t.z), pyq = u16(np);
  const cp = u16(nm), ct = bytes(nm), cc = bytes(nm);
  const qx = i16sum(nq, t.x), qz = i16sum(nq, t.z), qyq = u16(nq), qh = bytes(nq), qt = bytes(nq), qc = bytes(nq);
  const py = Float32Array.from(pyq, (v) => v / 100);
  // lanes: cumulative length per point (lane-local), heading per segment, bounding box
  const cs = new Float32Array(np), ang = new Float32Array(np);
  const L = { n: nl, start: new Int32Array(nl), npts: hPts, carStart: new Int32Array(nl), ncars: hCars,
    v: new Float32Array(nl), k: new Float32Array(nl), D: new Float32Array(nl), stop: new Float32Array(nl),
    len: new Float32Array(nl), P: new Float32Array(nl), lam: new Float32Array(nl), box: new Float32Array(nl * 6) };
  let ps = 0, pc = 0;
  for (let l = 0; l < nl; l++) {
    L.start[l] = ps; L.carStart[l] = pc;
    L.v[l] = (hSpeed[l] & 255) * 0.2; L.k[l] = (hSpeed[l] >> 8) / 100; L.D[l] = hD[l]; L.stop[l] = hStop[l] / 10;
    let s = 0, x0 = Infinity, z0 = Infinity, y0 = Infinity, x1 = -Infinity, z1 = -Infinity, y1 = -Infinity;
    for (let i = ps; i < ps + hPts[l]; i++) {
      if (i > ps) s += Math.hypot(px[i] - px[i - 1], pz[i] - pz[i - 1]);
      cs[i] = s;
      if (i < ps + hPts[l] - 1) ang[i] = Math.atan2(pz[i + 1] - pz[i], px[i + 1] - px[i]);
      else ang[i] = ang[i - 1];
      x0 = Math.min(x0, px[i]); x1 = Math.max(x1, px[i]); z0 = Math.min(z0, pz[i]); z1 = Math.max(z1, pz[i]);
      y0 = Math.min(y0, py[i]); y1 = Math.max(y1, py[i]);
    }
    L.box.set([x0, y0, z0, x1, y1, z1], l * 6);
    L.len[l] = s;
    L.stop[l] = Math.min(L.stop[l], s);
    const k = L.k[l];
    if (k >= 0.99) { L.P[l] = s; L.lam[l] = 1; } else {
      const lam = Math.log(1 / k) / (1 - k), D = Math.min(L.D[l], L.stop[l]);
      L.D[l] = D; L.lam[l] = lam;
      L.P[l] = (L.stop[l] - D) + (D + (s - L.stop[l])) * lam;
    }
    ps += hPts[l]; pc += hCars[l];
  }
  const colour = (types, cols) => {
    const a = new Float32Array(types.length), b = new Float32Array(types.length);
    for (let i = 0; i < types.length; i++) {
      const p = palettes[types[i]][cols[i]] ?? palettes[types[i]][0];
      a[i] = p[0]; b[i] = p[1];
    }
    return [a, b];
  };
  const [cA, cB] = colour(ct, cc), [qA, qB] = colour(qt, qc);
  const qy = Float32Array.from(qyq, (v) => v / 100);
  let qy0 = Infinity, qy1 = -Infinity;
  for (const v of qy) { qy0 = Math.min(qy0, v); qy1 = Math.max(qy1, v); }
  return {
    t, lanes: L, px, py, pz, cs, ang,
    cars: { n: nm, p0: Float32Array.from(cp, (v) => v / 10), type: ct, colA: cA, colB: cB },
    parked: { n: nq, x: qx, y: qy, y0: qy0, y1: qy1, z: qz,
      // (headings wrapped to [-pi, pi): the pose packs heading + 8 x fade level and unpacks the level as
      // floor((w + 4) / 8), so a heading of 4 rad or more (u8 >= 163) came back 8 rad short, the car turned
      // ~98 degrees across its neighbours: Singapore's Meadow car park, 7 Oct; a third of every city's parked cars)
      h: Float32Array.from(qh, (v) => (((v + 128) % 256 - 128) / 256) * 2 * Math.PI), type: qt, colA: qA, colB: qB },
  };
}

// position along a lane: free coordinate p -> distance s (the queue profile, see 06d_cars.py)
function warp(L, l, p) {
  const k = L.k[l];
  if (k >= 0.99) return p;
  const D = L.D[l], stop = L.stop[l], a = stop - D;
  if (p < a) return p;
  const q = p - a, pB = D * L.lam[l];
  if (q < pB) return a + D * (1 - Math.exp(-q * (1 - k) / D)) / (1 - k);
  const E = L.len[l] - stop;
  if (E <= 0) return stop;
  return stop + E * Math.min(1, (k * Math.exp((q - pB) * (1 - k) / E) - k) / (1 - k));
}

// ---------------------------------------------------------------- the module
// night: the uniforms from night.js (createNight().u), or null for cars that never switch their lights on
export async function createCars({ scene, camera, invalidate, envMap, terrain = null, night = null, url = 'cars/', sunShade = false, glass = null, shadowFade = 0, posts = false, keepOut = 0 }) {
  POSTS = posts;
  const index = await fetch(url + 'cars.json', { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  const group = new THREE.Group();
  group.name = 'cars';
  scene.add(group);
  const stats = { tiles: 0, lanes: 0, moving: 0, parked: 0, near: 0, far: 0, shadows: 0, triangles: 0, draws: 0, updateMs: 0, fillMs: 0 };
  if (!index) return { group, update() {}, active: () => false, stats, setDensity() {}, without: (fn) => fn() };

  const types = index.types;
  const tId = Object.fromEntries(types.map((t, i) => [t.name, i]));
  const palettes = types.map((t) => index.palettes[t.name].map(([a, b]) => [packHex(a), packHex(b)]));
  // far box and shadow layout per type (shares of height and length, see farMaterial)
  const FARINFO = {
    sedan: { belt: 0.64, cab: [0.2, 0.02, -0.2, -0.36], cargo: -1, winTop: 0.95, roofW: 0.72 },
    suv: { belt: 0.63, cab: [0.22, 0.06, -0.41, -0.48], cargo: -1, winTop: 0.95, roofW: 0.8 },
    taxi: { belt: 0.62, cab: [0.21, 0.03, -0.38, -0.48], cargo: -1, winTop: 0.95, roofW: 0.74 },
    van: { belt: 0.55, cab: [0.36, 0.19, -0.48, -0.5], cargo: -1, winTop: 0.95, roofW: 0.9 },
    bus: { belt: 0.33, cab: [0.5, 0.5, -0.5, -0.5], cargo: -1, winTop: 0.85, roofW: 0.95, transit: 1 },
    truck: { belt: 0.42, cab: [0.5, 0.5, -0.5, -0.5], cargo: 0.27, winTop: 0.72, roofW: 1 },
    lorry: { belt: 0.37, cab: [0.5, 0.5, -0.5, -0.5], cargo: 0.36, winTop: 0.64, roofW: 1 },
    hatch: { belt: 0.62, cab: [0.24, 0.005, -0.29, -0.43], cargo: -1, winTop: 0.95, roofW: 0.72 },
    crossover: { belt: 0.66, cab: [0.225, 0.0, -0.31, -0.45], cargo: -1, winTop: 0.95, roofW: 0.76 },
    bus_idfm: { belt: 0.33, cab: [0.5, 0.5, -0.5, -0.5], cargo: -1, winTop: 0.86, roofW: 0.95, silver: 1 },
    taxi_paris: { belt: 0.64, cab: [0.2, 0.02, -0.2, -0.36], cargo: -1, winTop: 0.95, roofW: 0.72 },
    taxi_london: { belt: 0.6, cab: [0.31, 0.16, -0.45, -0.49], cargo: -1, winTop: 0.92, roofW: 0.74 },
    // (silver 2: a double-decker, the box's glass in two bands, red between the decks, as busDDModel)
    bus_london: { belt: 0.255, cab: [0.5, 0.5, -0.5, -0.5], cargo: -1, winTop: 0.877, roofW: 0.95, silver: 2 },
    moto: { belt: 0.45, cab: [0.5, 0.5, -0.5, -0.5], cargo: -1, winTop: 0, roofW: 0.5 },
    bus_art: { belt: 0.33, cab: [0.5, 0.5, -0.5, -0.5], cargo: -1, winTop: 0.85, roofW: 0.95, transit: 1 },
    // (trams: the glass band lit at night like a bus's, silver 1)
    tram_cab: { belt: 0.29, cab: [0.5, 0.5, -0.5, -0.5], cargo: -1, winTop: 0.7, roofW: 0.9, silver: 1 },
    tram_mid: { belt: 0.29, cab: [0.5, 0.5, -0.5, -0.5], cargo: -1, winTop: 0.7, roofW: 0.9, silver: 1 },
    tram_tail: { belt: 0.29, cab: [0.5, 0.5, -0.5, -0.5], cargo: -1, winTop: 0.7, roofW: 0.9, silver: 1 },
  };
  // a type's model: cars.json's "model" (e.g. hatch, taxi_paris, bus_idfm), else its name
  const model = (t) => t.model ?? t.name;
  const info = types.map((t) => ({ ...t, ...(FARINFO[model(t)] ?? FARINFO[t.name] ?? FARINFO.sedan) }));
  const geoms = types.map((t) => {
    const k = model(t);
    if (k === 'bus' || k === 'bus_idfm') return busModel(t, k === 'bus_idfm');
    if (k === 'bus_london') return busDDModel(t);
    if (k === 'bus_art') return busArtModel(t);
    if (k === 'tram_cab' || k === 'tram_mid' || k === 'tram_tail') return tramModel(t, k.slice(5));
    if (k === 'truck') return truckModel(t);
    if (k === 'lorry') return lorryModel(t);
    if (k === 'moto') return motoModel(t);
    return carModel(MODELS[k] ?? MODELS[t.name] ?? MODELS.sedan, t);
  });
  const MOTO_T = tId.moto ?? -1;
  // (a tram's modules are never thinned one by one: setDensity keeps every train whole)
  const whole = types.map((t) => model(t).startsWith('tram_'));
  // (the lorry's corrugation: the type named lorry; cities whose types end lorry, moto keep it on index 6, the
  // moto drawing no second colour)
  U.lorryT.value = tId.lorry ?? -1;
  const near = nearMaterial(envMap, night, info);
  const far = farMaterial(envMap, info, night);
  if (glass) { U.glassK.value = glass.reflect ?? 0.45; U.glassTint.value = glass.tint ?? 1; U.transitK.value = glass.transit ?? 1; }
  let sunLight = null;
  if (sunShade) scene.traverse((o) => { if (o.isDirectionalLight && o.castShadow && !sunLight) sunLight = o; });
  const shadowMat = shadowMaterial(far, sunLight, shadowFade);

  const all = [];
  const make = (name, base, mat) => {
    const mesh = new THREE.Mesh(new THREE.InstancedBufferGeometry(), mat);
    mesh.frustumCulled = false;
    mesh.visible = false;
    mesh.castShadow = false;                 // planar shadows instead (see the header)
    mesh.receiveShadow = mat !== shadowMat;
    mesh.name = name;
    mesh.userData = { base, cap: 0, n: 0, nStatic: 0, pose: null, look: null, tris: base.attributes.position.count / 3 };
    group.add(mesh);
    all.push(mesh);
    return mesh;
  };
  types.forEach((t, i) => make(`cars-${t.name}`, geoms[i], near));
  const FARM = types.length, SHAD = types.length + 1;
  make('cars-far', unitBox(), far.m);
  const shadowMesh = make('cars-shadow', shadowHull(), shadowMat);
  shadowMesh.renderOrder = 1;
  function ensure(mesh, n) {
    const u = mesh.userData;
    if (n <= u.cap) return;
    u.cap = Math.ceil(n * 1.3 / 1024) * 1024;
    const g = new THREE.InstancedBufferGeometry();
    for (const k of Object.keys(u.base.attributes)) g.setAttribute(k, u.base.attributes[k]);
    u.pose = new THREE.InstancedBufferAttribute(new Float32Array(u.cap * 4), 4);
    u.look = new THREE.InstancedBufferAttribute(new Float32Array(u.cap * 4), 4);
    u.pose.setUsage(THREE.DynamicDrawUsage);
    u.look.setUsage(THREE.DynamicDrawUsage);
    g.setAttribute('pose', u.pose);
    g.setAttribute('look', u.look);
    mesh.geometry.dispose();
    mesh.geometry = g;
  }

  // ---- tiles
  const tiles = index.tiles.map((t) => ({ ...t, state: 'idle', data: null }));
  let inflight = 0, needFill = true;
  // (the camera's height above the ground under it counts, not above the sea)
  let camGround = 0;
  const tileDist2 = (t, p) => {
    const dx = Math.max(t.x - p.x, 0, p.x - t.x - 1000), dz = Math.max(t.z - p.z, 0, p.z - t.z - 1000);
    const dy = Math.max(p.y - camGround, 0);
    return dx * dx + dz * dz + dy * dy;
  };
  async function load(t) {
    t.state = 'loading';
    inflight++;
    try {
      const buf = await gunzip(await (await fetch(url + t.file)).arrayBuffer());
      if (t.state === 'loading') { t.data = decodeTile(buf, t, palettes); t.state = 'ready'; }
    } catch (e) {
      console.warn('cars: tile failed', t.file, e);
      t.state = 'failed';
    }
    inflight--;
    needFill = true;
    invalidate({ redraw: true });   // (an arrival, not a move: see main.js)
  }
  function stream(p) {
    const want = [];
    for (const t of tiles) {
      const d2 = tileDist2(t, p);
      if (t.state === 'idle' && d2 < LOAD ** 2) want.push([d2, t]);
      else if ((t.state === 'ready' || t.state === 'loading') && d2 > DROP ** 2) { t.state = 'idle'; t.data = null; }
    }
    want.sort((a, b) => a[0] - b[0]);
    for (const [, t] of want) {
      if (inflight >= CONCURRENCY) break;
      load(t);
    }
  }

  // ---- placing cars: one car into the buffers of its level of detail (and the shadow's)
  const cam = new THREE.Vector3();
  let density = 1;
  const put = (mi, x, y, z, w, a, b, type, seed) => {
    const u = all[mi].userData, k = u.n++;
    u.pose.array[k * 4] = x; u.pose.array[k * 4 + 1] = y; u.pose.array[k * 4 + 2] = z; u.pose.array[k * 4 + 3] = w;
    u.look.array[k * 4] = a; u.look.array[k * 4 + 1] = b; u.look.array[k * 4 + 2] = type; u.look.array[k * 4 + 3] = seed;
  };
  const place = (x, y, z, h, fade, a, b, type, seed) => {
    const dx = x - cam.x, dy = y - cam.y, dz = z - cam.z;
    const d2 = dx * dx + dy * dy + dz * dz;
    if (d2 > FAR * FAR || fade <= 0) return;
    const w = h + 8 * Math.round(Math.min(1, fade) * 15);
    put(d2 < NEAR * NEAR ? type : FARM, x, y, z, w, a, b, type, seed);
    if (d2 < SHADOW * SHADOW) put(SHAD, x, y, z, w, a, b, type, seed);
  };
  const FADE = index.fade ?? 4;
  // a moving car's pose at time t
  function laneCar(d, l, i, time) {
    const L = d.lanes, P = L.P[l];
    const p = (d.cars.p0[i] + L.v[l] * time) % P;
    const s = warp(L, l, p);
    const a = L.start[l], n = L.npts[l];
    let lo = a, hi = a + n - 1;                     // binary search: cs[lo] <= s < cs[lo + 1]
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (d.cs[mid] <= s) lo = mid; else hi = mid; }
    const seg = Math.max(d.cs[lo + 1] - d.cs[lo], 1e-6), f = Math.min(1, Math.max(0, (s - d.cs[lo]) / seg));
    // heading eases into the next segment's over the last 2 m before a bend
    let h = d.ang[lo];
    const toEnd = d.cs[lo + 1] - s;
    if (toEnd < 2 && lo + 1 < a + n - 1) {
      let dh = d.ang[lo + 1] - h;
      dh -= Math.round(dh / (2 * Math.PI)) * 2 * Math.PI;
      h += dh * 0.5 * (1 - toEnd / 2);
    }
    h -= Math.round(h / (2 * Math.PI)) * 2 * Math.PI;
    // at a lane piece's ends (the junctions) a car appears or goes whole: dissolving over a few metres left
    // half-drawn ghosts on the crossings in any frame the traffic stopped on
    const fade = Math.min(s, L.len[l] - s) >= FADE / 2 ? 1 : 0;
    const k = d.cars.type[i];
    // two-wheelers keep to one side of the lane or the other (by the car's rank), not its middle; at most
    // 0.4 m off it, so a 0.75 m wide bike stays clear of the lane lines in the narrowest lane (2.7 m,
    // 06d_cars.py LANE_MIN) instead of riding on them
    const side = k === MOTO_T ? (((i * 0.3819) % 1) - 0.5) * 0.8 : 0;
    const x = d.px[lo] + (d.px[lo + 1] - d.px[lo]) * f - Math.sin(h) * side, z = d.pz[lo] + (d.pz[lo + 1] - d.pz[lo]) * f + Math.cos(h) * side;
    // (city.json cars.keepOut, m, off by default: a street-level camera standing on a lane is not driven through; the
    // cars within that radius of it are left out, as at a lane's ends. Berlin M9 fix round: Oranienstraße's overlay)
    const out = keepOut > 0 && cam.y - camGround < 25 && (x - cam.x) ** 2 + (z - cam.z) ** 2 < keepOut * keepOut;
    place(x, d.py[lo] + (d.py[lo + 1] - d.py[lo]) * f, z, h, out ? 0 : fade, d.cars.colA[i], d.cars.colB[i], k, (i * 0.618034) % 1);
  }
  // keep a share `density` of the cars (for a quieter city); by a fixed per-car rank
  const kept = (i, salt) => ((i * 0.754877 + salt * 0.569840) % 1) < density;

  // ---- refill: static cars (parked, and moving ones on lanes beyond ANIM) and the list of animated lanes
  const frustum = new THREE.Frustum(), projView = new THREE.Matrix4(), bbox = new THREE.Box3();
  let dynamic = [];                                  // [tile data, lane index]
  let dynCount = 0, lastTime = 0;
  function fill(time) {
    const t0 = performance.now();
    cam.copy(camera.position);
    camGround = terrain ? terrain.height(cam.x, cam.z) : 0;
    camera.updateMatrixWorld();
    projView.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    frustum.setFromProjectionMatrix(projView, camera.coordinateSystem, camera.reversedDepth);   // (the camera's own depth convention)
    const list = tiles.filter((t) => t.state === 'ready' && tileDist2(t, cam) < (FAR + 1200) ** 2).map((t) => t.data);
    // capacities: every car that could be drawn from these tiles, by type
    const byType = new Array(types.length).fill(0);
    dynamic = [];
    const still = [];                                // lanes beyond ANIM: their cars are placed now only
    dynCount = 0;
    let parkedN = 0, lanesN = 0;
    for (const d of list) {
      const L = d.lanes;
      for (let l = 0; l < L.n; l++) {
        const b = L.box, o = l * 6;
        const dx = Math.max(b[o] - cam.x, 0, cam.x - b[o + 3]), dz = Math.max(b[o + 2] - cam.z, 0, cam.z - b[o + 5]);
        const dy = Math.max(b[o + 1] - cam.y, 0, cam.y - b[o + 4]);
        const d2 = dx * dx + dy * dy + dz * dz;
        if (d2 > FAR * FAR) continue;
        bbox.min.set(b[o] - 10, b[o + 1] - 1, b[o + 2] - 10);
        bbox.max.set(b[o + 3] + 10, b[o + 4] + 5, b[o + 5] + 10);
        if (!frustum.intersectsBox(bbox)) continue;
        lanesN++;
        const c0 = L.carStart[l];
        for (let i = c0; i < c0 + L.ncars[l]; i++) byType[d.cars.type[i]]++;
        if (d2 < ANIM * ANIM) { dynamic.push(d, l); dynCount += L.ncars[l]; } else still.push(d, l);
      }
      const t = d.t;
      bbox.min.set(t.x - 10, d.parked.y0 - 1, t.z - 10);
      bbox.max.set(t.x + 1010, d.parked.y1 + 5, t.z + 1010);
      if (d.parked.n && tileDist2(t, cam) < FAR * FAR && frustum.intersectsBox(bbox)) {
        d.parkedOn = true;
        for (let i = 0; i < d.parked.n; i++) byType[d.parked.type[i]]++;
        parkedN += d.parked.n;
      } else d.parkedOn = false;
    }
    const total = byType.reduce((a, b) => a + b, 0);
    all.forEach((m, j) => { ensure(m, j < types.length ? byType[j] : total); m.userData.n = 0; });
    // static part
    for (const d of list) {
      if (!d.parkedOn) continue;
      const q = d.parked;
      for (let i = 0; i < q.n; i++) {
        if (!kept(i, 7)) continue;
        place(q.x[i], q.y[i], q.z[i], q.h[i], 1, q.colA[i], q.colB[i], q.type[i], 1 + (i * 0.618034) % 1);   // parked: lights off
      }
    }
    for (let j = 0; j < still.length; j += 2) {
      const d = still[j], l = still[j + 1], c0 = d.lanes.carStart[l];
      for (let i = c0; i < c0 + d.lanes.ncars[l]; i++) if (whole[d.cars.type[i]] || kept(i, 3)) laneCar(d, l, i, time);
    }
    for (const m of all) m.userData.nStatic = m.userData.n;
    Object.assign(stats, { tiles: list.length, lanes: lanesN, parked: parkedN, moving: dynCount, fillMs: +(performance.now() - t0).toFixed(1) });
    needFill = false;
    return true;
  }

  // per frame: the animated lanes' cars after the static ones
  function animateCars(time, full) {
    const t0 = performance.now();
    for (const m of all) m.userData.n = m.userData.nStatic;
    for (let j = 0; j < dynamic.length; j += 2) {
      const d = dynamic[j], l = dynamic[j + 1], c0 = d.lanes.carStart[l];
      for (let i = c0; i < c0 + d.lanes.ncars[l]; i++) if (whole[d.cars.type[i]] || kept(i, 3)) laneCar(d, l, i, time);
    }
    stats.triangles = stats.draws = stats.near = 0;
    all.forEach((m, j) => {
      const u = m.userData;
      m.visible = u.n > 0;
      if (!u.pose) return;
      m.geometry.instanceCount = u.n;
      if (m.visible) { stats.draws++; stats.triangles += u.n * u.tris; }
      if (j < types.length) stats.near += u.n;
      const from = full ? 0 : u.nStatic;
      for (const a of [u.pose, u.look]) {
        a.clearUpdateRanges();
        a.addUpdateRange(from * 4, Math.max(1, (u.n - from) * 4));
        a.needsUpdate = true;
      }
    });
    stats.far = all[FARM].userData.n;
    stats.shadows = all[SHAD].userData.n;
    stats.updateMs = +(performance.now() - t0).toFixed(2);
  }

  const sun = (() => { let s = null; scene.traverse((o) => { if (o.isDirectionalLight && !s) s = o; }); return s; })();
  const lastPos = new THREE.Vector3(Infinity, 0, 0), lastQuat = new THREE.Quaternion();
  let lastFill = 0;
  // time: seconds of traffic (a clock that only runs while the view animates); moving: the camera moves
  function update(time, moving = false) {
    if (!group.visible) return;
    lastTime = time;
    U.camPos.value.copy(camera.position);
    if (sun) {
      U.sunDir.value.copy(sun.position).sub(sun.target.position).normalize();
      U.sunUp.value = THREE.MathUtils.smoothstep(U.sunDir.value.y, 0.03, 0.2) * Math.min(1, sun.intensity / 2);
    }
    const p = camera.position;
    stream(p);
    const now = performance.now();
    const movedCam = p.distanceTo(lastPos) > Math.max(5, 0.02 * p.y) || camera.quaternion.angleTo(lastQuat) > 0.03;
    let full = false;
    if ((needFill || movedCam) && !(moving && now - lastFill < REFILL_MS)) {
      fill(time);
      full = true;
      lastFill = now;
      lastPos.copy(p);
      lastQuat.copy(camera.quaternion);
    }
    animateCars(time, full);
  }
  return {
    group, update, stats, meshes: all, index,
    // whether moving cars are near enough to be worth animating
    active: () => group.visible && dynCount > 0,
    // run fn with every car mesh drawing nothing (still in the render lists, see main.js's AO pre-pass)
    without: (fn) => {
      const saved = all.map((m) => m.geometry.instanceCount);
      for (const m of all) m.geometry.instanceCount = 0;
      try { return fn(); } finally { all.forEach((m, i) => { m.geometry.instanceCount = saved[i]; }); }
    },
    setDensity: (k) => { density = Math.max(0, Math.min(1, k)); needFill = true; update(lastTime); invalidate(); },
  };
}
