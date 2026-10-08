#!/usr/bin/env python3
"""M7 Merlion: photo-referenced low-poly model of the Merlion statue (Merlion Park).

Builds, procedurally with numpy/trimesh, a ~10k-triangle model of the Merlion
(1972, sculptor Lim Nang Seng, white cement, 8.6 m tall, 70 t) and writes it to
demos/data/singapore/models/merlion.obj.  Units metres, +Y up, +Z = the way the
lion looks and the mouth spouts, +X = the statue's right.  Lowest point y=0
(base of the wave plinth), body centred on x=z=0, top of the mane y=8.6.
Every part is a closed, consistently wound (CCW from outside) solid; parts
overlap (the engine slices/merges/simplifies).  Single colour, so the shape
carries it: shingle tiers of the mane, fluted face frame, mouth recess, fish
scale rows, the scalloped tail fan, the wave-ridge plinth.

Reference photos (Wikimedia Commons, looked at while building):
  "Merlion Side View at Night.JPG" (clean side silhouette; main proportions),
  "Rear view of the Merlion statue at Merlion Park ... 20140307.jpg",
  "Merlion Closeup Large.JPG" (face: eye, brow, ear, whiskers, fangs, mouth,
  fluted mane edge, spout pipe), "The Merlion, Singapore.jpg" and
  "Singapore Merlion-at-Marina-Bay-01.jpg" (3/4 front: chest bib, hooked
  pectoral fin under the chin, tail fan at the front-lower body with the round
  eyelet), "Merlion statue at Tourism Court ... 20150329.jpg" (replica, full
  side), "Singapore Merlion-at-Marina-Bay-03" (high view of the wave plinth).

What the photos show (and the brief's mental image did not): the mane is NOT a
ring of curls but a smooth fluted hood that hangs down the back as THREE
stacked, widening shingle tiers with flared flat lips; the mane + head is about
half of the height (mane lip ~4.1 m up, chin ~6.4 m), not 35-40 %; the scaled
fish body is a plain column (about 2.2 m wide, ~2.7 m deep) with rows of fan
scales, a bib below the chin, a hooked pectoral fin under the chin, a round
eyelet at the lower side and the scalloped tail fan curling at the FRONT-lower
body (there is no tall tail rising behind); the plinth is a long, striped
wave with crest ridges, about 1.1 m high.

Dimensions: height 8.6 m; mane 3.3 m wide, back at z=-1.7; nose z=+2.3;
body 2.5 m wide; plinth 3.8 m x 6 m x ~1.1 m.  Mouth/spout pipe tip at about
(0, 6.45, 1.8).  Run:  uv run python scripts/m7_merlion.py [--no-preview]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
OUT_OBJ = HERE.parents[1] / "data" / "singapore" / "models" / "merlion.obj"
PREVIEW_DIR = Path(os.environ.get(
    "MERLION_PREVIEW_DIR",
    str(HERE.parents[1] / "data" / "singapore" / "merlion-preview")))
TOP = 8.6
TAU = 2 * np.pi


# ---------------------------------------------------------------- helpers
def rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def sstep(x, a=0.0, b=1.0):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def spow(x, p):
    return np.sign(x) * np.abs(x) ** p


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def finish(V, F):
    """Weld, drop degenerate faces, make outward (positive volume) winding."""
    m = trimesh.Trimesh(np.asarray(V, float), np.asarray(F, int), process=False)
    m.merge_vertices(digits_vertex=6)
    m.update_faces(m.nondegenerate_faces(height=1e-7))
    m.remove_unreferenced_vertices()
    V, F = m.vertices.copy(), m.faces.copy()
    vol = np.einsum("ij,ij->i", V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])).sum() / 6
    if vol < 0:
        F = F[:, ::-1]
    return V, F


def ellipsoid(c, r, rot=None, nu=10, nv=7, fn=None):
    th = np.arange(nu) * TAU / nu
    ph = np.pi * np.arange(1, nv) / nv
    P = [[0, 1, 0]]
    for p in ph:
        for t in th:
            P.append([np.sin(p) * np.cos(t), np.cos(p), np.sin(p) * np.sin(t)])
    P.append([0, -1, 0])
    P = np.array(P) * np.asarray(r, float)
    if fn is not None:
        P = fn(P)
    if rot is not None:
        P = P @ np.asarray(rot).T
    P = P + np.asarray(c, float)
    F = []
    for j in range(nu):
        F.append([0, 1 + (j + 1) % nu, 1 + j])
    for i in range(nv - 2):
        for j in range(nu):
            a, b = 1 + i * nu + j, 1 + i * nu + (j + 1) % nu
            cc, d = 1 + (i + 1) * nu + (j + 1) % nu, 1 + (i + 1) * nu + j
            F += [[a, b, cc], [a, cc, d]]
    last = len(P) - 1
    for j in range(nu):
        F.append([last, 1 + (nv - 2) * nu + j, 1 + (nv - 2) * nu + (j + 1) % nu])
    return finish(P, F)


def ring_solid(R, c0=None, c1=None):
    """Closed solid from rings R (n, m, 3), end caps fanned to centres."""
    n, m, _ = R.shape
    c0 = R[0].mean(0) if c0 is None else c0
    c1 = R[-1].mean(0) if c1 is None else c1
    P = np.concatenate([R.reshape(-1, 3), [c0], [c1]])
    i0, i1 = n * m, n * m + 1
    F = []
    for i in range(n - 1):
        for j in range(m):
            j2 = (j + 1) % m
            a, b = i * m + j, i * m + j2
            cc, d = (i + 1) * m + j2, (i + 1) * m + j
            F += [[a, b, cc], [a, cc, d]]
    for j in range(m):
        j2 = (j + 1) % m
        F.append([i0, j2, j])
        F.append([i1, (n - 1) * m + j, (n - 1) * m + j2])
    return finish(P, F)


def tube(spine, a_of_s, b_of_s, side, up, m=10, cap_scale=0.0):
    """Tube along spine (n,3); elliptic section a (along `side`) x b (along `up`)."""
    n = len(spine)
    s = np.linspace(0, 1, n)
    a, b = a_of_s(s), b_of_s(s)
    side = np.broadcast_to(side, (n, 3))
    up = np.broadcast_to(up, (n, 3))
    th = np.arange(m) * TAU / m
    R = (spine[:, None, :] + a[:, None, None] * np.cos(th)[None, :, None] * side[:, None, :]
         + b[:, None, None] * np.sin(th)[None, :, None] * up[:, None, :])
    return ring_solid(R)


def lens(P, N, t):
    """Closed shell between surface P (grid) and P + N*t; t==0 on the border."""
    nr, na, _ = P.shape
    Fr = P + N * t[..., None]
    V = np.concatenate([Fr.reshape(-1, 3), P.reshape(-1, 3)])
    off = nr * na
    F = []
    for i in range(nr - 1):
        for j in range(na - 1):
            a, b, c, d = i * na + j, i * na + j + 1, (i + 1) * na + j + 1, (i + 1) * na + j
            F += [[a, b, c], [a, c, d]]
            F += [[off + a, off + c, off + b], [off + a, off + d, off + c]]
    return finish(V, F)


def join(parts):
    Vs, Fs, o = [], [], 0
    for V, F in parts:
        Vs.append(V)
        Fs.append(F + o)
        o += len(V)
    return np.concatenate(Vs), np.concatenate(Fs)


# ---------------------------------------------------------------- body
# fish body: a plain column, y-parametrised ellipse sections
BY = np.array([0.8, 1.4, 2.2, 3.0, 3.8, 4.5, 5.4, 6.4])
BA = np.array([1.18, 1.28, 1.28, 1.20, 1.10, 1.00, 0.92, 0.85])
BB = np.array([1.05, 1.20, 1.25, 1.15, 1.00, 0.90, 0.80, 0.75])
BZ = np.array([0.00, -0.20, -0.25, -0.20, -0.05, 0.10, 0.25, 0.30])


def body_a(y): return np.interp(y, BY, BA)
def body_b(y): return np.interp(y, BY, BB)
def body_z(y): return np.interp(y, BY, BZ)


def body_part():
    ys = np.concatenate([np.arange(0.8, 4.7, 0.09), np.arange(4.7, 6.41, 0.34)])
    ys = ys[::-1]  # top -> bottom, scale rows hang from the top
    ns = 10        # scales around
    m = 40
    th = np.arange(m) * TAU / m
    rows_y = 4.75   # row 0 hangs from here
    L0 = 0.36
    R = np.zeros((len(ys), m, 3))
    for i, y in enumerate(ys):
        a, b, zc = body_a(y), body_b(y), body_z(y)
        # row coordinate (monotone in y); scale rows shrink a little toward the bottom
        q = (rows_y - y) / L0
        k = np.floor(q)
        f = q - k
        d = ((th / TAU * ns + 0.5 * (k % 2)) % 1.0) - 0.5
        fe = 1 - 0.55 * (2 * d) ** 2
        h = np.where(f < fe, (f / fe) ** 1.3, 1 - 0.55 * (f - fe) / (1 - fe + 1e-9))
        amp = 0.10 * (1 - sstep(y, 4.5, 5.2))
        amp = amp * np.where(y < 4.75, 1.0, 0.0) if y < rows_y else 0.0
        hh = amp * h
        cx, sz = np.cos(th), np.sin(th)
        x = (a + hh) * cx
        z = zc + (b + hh) * sz
        yy = np.full(m, y)
        # round eyelet dimple on both sides (photo: hole at the lower side)
        dd = np.hypot(yy - 2.3, z - 0.65)
        dim = -0.20 * np.exp(-(dd / 0.22) ** 2) + 0.07 * np.exp(-((dd - 0.36) / 0.10) ** 2)
        x = x + np.where(np.abs(cx) > 0.5, -np.sign(cx) * dim, 0.0)
        R[i] = np.stack([x, yy, z], axis=1)
    return ring_solid(R)


def tail_fan():
    """Scalloped, ribbed tail fan lying on the FRONT of the lower body."""
    nr, na = 7, 40
    amin, amax = np.radians(-60), np.radians(60)
    al = np.linspace(amin, amax, na)
    rho = np.linspace(0.07, 1.0, nr)
    y0, rmax = 0.85, 1.85
    period = np.radians(24)
    f = ((al - amin) / period) % 1.0
    lobe = np.sqrt(np.clip(1 - (2 * f - 1) ** 2, 0, 1)) ** 0.8
    rim = rmax * (0.70 + 0.30 * lobe) * (1 - 0.18 * (al / amax) ** 2)
    P = np.zeros((nr, na, 3))
    N = np.zeros((nr, na, 3))
    t = np.zeros((nr, na))
    for i, rr in enumerate(rho):
        r = rr * rim
        x = 0.82 * r * np.sin(al)
        y = y0 + r * np.cos(al)
        zb = body_z(y) + body_b(y) * np.sqrt(np.clip(1 - (x / body_a(y)) ** 2, 0.04, 1)) + 0.09
        zb = zb + 0.30 * rr ** 2.2          # the fan flares forward as it rises
        P[i, :, 0], P[i, :, 1], P[i, :, 2] = x, y, zb
        N[i] = unit(np.stack([x * 0.5, np.zeros(na), np.ones(na)], 1))
        ribs = 0.72 + 0.28 * np.cos((al - amin) / period * TAU * 2)
        bump = np.sin(np.pi * np.clip((rr - 0.07) / 0.93, 0, 1)) ** 0.7
        taper = np.sin(np.pi * (al - amin) / (amax - amin)) ** 0.45
        t[i] = 0.42 * bump * taper * ribs
    t[:, 0] = 0
    t[:, -1] = 0
    t[0] = 0
    t[-1] = 0
    return lens(P, N, t)


def pectoral_fins():
    """Short flat hooked fin pressed on the chest/bib (about 0.8 m long, 0.1 m proud)."""
    from scipy.interpolate import CubicSpline
    out = []
    for sx in (-1, 1):
        xy = np.array([[0.30, 4.50], [0.38, 4.78], [0.50, 4.98], [0.66, 5.08], [0.78, 5.04]])
        cs = CubicSpline(np.linspace(0, 1, len(xy)), xy)
        s_ = np.linspace(0, 1, 11)
        px, py = cs(s_).T
        pz = body_z(py) + body_b(py) * np.sqrt(np.clip(1 - (px / body_a(py)) ** 2, 0.04, 1)) + 0.05
        sp = np.stack([sx * px, py, pz], 1)
        T = unit(np.gradient(sp, axis=0))
        nrm = unit(np.stack([sx * px * 0.4, np.zeros_like(px), np.ones_like(px)], 1))
        side = unit(np.cross(T, nrm))
        upv = unit(np.cross(side, T))
        tipk = np.sqrt(np.clip(1 - sstep(s_, 0.82, 1.0) ** 2, 0.04, 1))
        a_ = (0.14 + 0.09 * sstep(s_, 0.3, 0.8)) * tipk          # width across the fin
        b_ = (0.09 + 0.03 * np.sin(np.pi * s_)) * tipk            # thickness (flat)
        th = np.arange(8) * TAU / 8
        R = (sp[:, None, :] + a_[:, None, None] * np.cos(th)[None, :, None] * side[:, None, :]
             + b_[:, None, None] * np.sin(th)[None, :, None] * nrm[:, None, :])
        out.append(ring_solid(R))
    return join(out)


# ---------------------------------------------------------------- mane
def superellipse_tier(rings, n_exp=3.0, m=48, notch=0.85, groove=0.045, kg=12):
    """rings: list of (y, X, Zb, Zf, zc[, pt]).  Closed tier solid, flat-capped.  The plan is a
    superellipse whose front is notched (U-shaped) so the mane wraps the face sides; `pt`
    pulls pointed corners out at the sides and back corners (the flared lip); shallow
    vertical grooves on the back/sides."""
    th = np.arange(m) * TAU / m
    cx, sn = np.cos(th), np.sin(th)
    ex = 2.0 / n_exp
    R = []
    for rg in rings:
        y, X, Zb, Zf, zc = rg[:5]
        pt = rg[5] if len(rg) > 5 else 0.0
        x = X * spow(cx, ex)
        zz = np.where(sn < 0, Zb, Zf) * spow(sn, ex)
        gr = 1 - groove * (0.5 + 0.5 * np.cos(kg * th)) * sstep(-sn, -0.15, 0.25) * sstep(y, 4.3, 4.9)
        x, zz = x * gr, zz * gr
        # pointed corners: side tips at +-x and back corners at 225/315 deg
        tip = np.exp(-((sn) / 0.30) ** 2) + 0.6 * np.exp(-((np.abs(cx) - 0.72) / 0.18) ** 2) * (sn < 0)
        x = x * (1 + pt * tip)
        zz = zz * (1 + 0.5 * pt * np.exp(-((np.abs(cx) - 0.72) / 0.18) ** 2) * (sn < 0))
        z = zc + zz
        k = min(1.0, max(0.0, (y - 6.0) / 0.8)) * 0.15 + 0.85
        z = z - np.where(sn > 0, notch * k * sstep(X, 0.5, 1.1) * np.exp(-(x / (0.50 * X + 0.45)) ** 4) * np.minimum(1, zz / 0.3), 0)
        R.append(np.stack([x, np.full(m, y), z], 1))
    return ring_solid(np.array(R))


def mane_part():
    zc = -0.55
    parts = []
    # tier 1: crown dome flowing into the first flared lip
    t1 = [(8.60, 0.30, 0.30, 0.30, zc + 0.10), (8.52, 0.80, 0.55, 0.85, zc + 0.05),
          (8.30, 1.06, 0.68, 1.30, zc), (7.9, 1.16, 0.74, 1.45, zc), (7.2, 1.22, 0.80, 1.45, zc),
          (6.6, 1.28, 0.84, 1.45, zc), (6.24, 1.36, 0.88, 1.45, zc, 0.10), (6.16, 1.30, 0.80, 1.40, zc, 0.15),
          (6.12, 1.22, 0.70, 1.30, zc, 0.10)]
    # tier 2
    t2 = [(6.75, 1.08, 0.70, 1.25, zc), (6.2, 1.32, 0.90, 1.45, zc), (5.7, 1.42, 0.98, 1.45, zc),
          (5.34, 1.50, 1.04, 1.45, zc, 0.10), (5.26, 1.42, 0.97, 1.40, zc, 0.16), (5.22, 1.36, 0.88, 1.30, zc, 0.10)]
    # tier 3 (widest, lowest lip)
    t3 = [(5.8, 1.12, 0.78, 1.25, zc), (5.3, 1.42, 1.02, 1.45, zc), (4.8, 1.54, 1.12, 1.45, zc),
          (4.39, 1.62, 1.18, 1.45, zc, 0.12), (4.31, 1.52, 1.10, 1.40, zc, 0.17), (4.27, 1.50, 0.98, 1.30, zc, 0.12)]
    for tier in (t1, t2, t3):
        parts.append(superellipse_tier(tier, 3.2))
    # crown tufts at the back
    for sx in (-1, 1):
        parts.append(ellipsoid((0.50 * sx, 8.50, -0.80), (0.24, 0.24, 0.18), rz(-0.30 * sx), 8, 5))
    return join(parts)


# ---------------------------------------------------------------- face
def jaw(z0, z1, hw0, hw1, hh, yc0, yc1, dent_up, n=10, m=22, front_round=0.22, dent=0.78):
    """Lofted jaw along +z with a dished inner side (dent_up: dent on the top)."""
    th = np.arange(m) * TAU / m
    rings = []
    for s in np.linspace(0, 1, n):
        z = z0 + (z1 - z0) * s
        hw = hw0 + (hw1 - hw0) * s
        yc = yc0 + (yc1 - yc0) * s
        k = np.sqrt(np.clip(1 - sstep(s, 1 - front_round, 1.0) ** 2, 0.0, 1)) if s < 1 else 0.0
        k = max(k, 0.12)
        x = hw * k * spow(np.cos(th), 0.75)
        y = hh * k * spow(np.sin(th), 0.8)
        g = np.exp(-(x / (0.62 * hw * k + 1e-6)) ** 2)
        if dent_up:
            y = np.where(y > 0, y * (1 - dent * g), y)
        else:
            y = np.where(y < 0, y * (1 - dent * g), y)
        rings.append(np.stack([x, yc + y, np.full(m, z)], 1))
    return ring_solid(np.array(rings))


def cone(base, direction, length, r, m=6):
    d = unit(np.asarray(direction, float))
    a = unit(np.cross(d, [1, 0, 0.3]))
    b = np.cross(d, a)
    th = np.arange(m) * TAU / m
    ring = base + r * (np.cos(th)[:, None] * a + np.sin(th)[:, None] * b)
    R = np.stack([ring, base + d * length * 0.999 + 0.004 * (np.cos(th)[:, None] * a + np.sin(th)[:, None] * b)])
    return ring_solid(R)


def face_part():
    P = []
    P.append(ellipsoid((0, 7.55, 0.15), (0.82, 0.84, 0.88), None, 16, 10))               # skull
    P.append(jaw(0.55, 1.95, 0.74, 0.60, 0.44, 7.0, 7.1, dent_up=False, n=10))        # upper jaw/muzzle
    P.append(ellipsoid((0, 7.27, 1.88), (0.42, 0.24, 0.27), rx(0.15), 10, 6))           # nose pad
    P.append(ellipsoid((0, 7.62, 1.35), (0.23, 0.22, 0.80), rx(0.28), 8, 6))           # nose bridge
    # mouth interior / throat
    P.append(ellipsoid((0, 6.88, 0.55), (0.42, 0.34, 0.40), None, 10, 6))
    # lower jaw hinged below the cheeks, dropped ~24 deg, with a dished top
    V, F = jaw(0.0, 1.45, 0.52, 0.36, 0.32, 0.0, 0.0, dent_up=True, n=9, dent=0.72)
    V = V @ rx(np.radians(24)).T + np.array([0, 6.80, 0.50])
    P.append((V, F))
    # tongue in the lower jaw trough
    P.append(ellipsoid((0, 6.62, 1.05), (0.20, 0.07, 0.50), rx(np.radians(24)), 8, 4))
    # spout pipe poking out of the mouth
    pipe = np.array([[0, 6.50, 0.85], [0, 6.50, 1.80]])
    th = np.arange(8) * TAU / 8
    Rr = np.array([pipe[i] + 0.12 * np.stack([np.cos(th), np.sin(th), 0 * th], 1) for i in range(2)])
    P.append(ring_solid(Rr))
    # teeth: canines and a few lower
    for sx in (-1, 1):
        P.append(cone(np.array([0.31 * sx, 6.70, 1.60]), (0, -1, 0.15), 0.34, 0.09))
        Vt, Ft = cone(np.array([0.24 * sx, 0.20, 1.05]), (0, 1, 0.1), 0.26, 0.075)
        Vt = Vt @ rx(np.radians(24)).T + np.array([0, 6.80, 0.50])
        P.append((Vt, Ft))
        # brows, eyes, cheeks, whisker pads, ears
        P.append(ellipsoid((0.46 * sx, 7.94, 0.80), (0.40, 0.15, 0.40), rz(-0.18 * sx), 10, 6))
        P.append(ellipsoid((0.46 * sx, 7.70, 0.84), (0.17, 0.15, 0.11), None, 8, 5))
        P.append(ellipsoid((0.64 * sx, 7.05, 0.40), (0.36, 0.44, 0.50), None, 10, 7))
        P.append(ellipsoid((0.32 * sx, 6.92, 1.50), (0.28, 0.20, 0.40), rx(0.1), 9, 5))
        P.append(ellipsoid((0.68 * sx, 8.22, 0.45), (0.22, 0.28, 0.12), rz(-0.35 * sx) @ rx(-0.15), 8, 5))
    return join(P)


# ---------------------------------------------------------------- plinth
def plinth_part():
    na, nr = 60, 12
    zc0, Rx, Rz = 0.15, 1.95, 3.0
    th = np.arange(na) * TAU / na
    # superellipse outline, lumpy
    ex = 2 / 2.6
    ox = Rx * spow(np.cos(th), ex) * (1 + 0.05 * np.sin(5 * th + 1))
    oz = zc0 + Rz * spow(np.sin(th), ex) * (1 + 0.06 * np.sin(4 * th))
    V = [[0, 0, zc0]]
    rings = []
    rho = np.linspace(1 / nr, 1, nr)
    for r in rho:
        x = ox * r
        z = zc0 + (oz - zc0) * r
        s = sstep(1 - r, 0, 0.34)
        edge = 1 - (1 - s) ** 2
        Hmax = 0.98 - 0.42 * sstep(z, 0.6, 3.2) + 0.14 * np.exp(-((z + 2.0) / 0.6) ** 2)
        ph = ((x + 0.30 * np.sin(1.1 * z)) / 0.85 + 0.25) % 1.0
        saw = np.where(ph < 0.72, (ph / 0.72) ** 1.6, 1 - (ph - 0.72) / 0.28)   # slow rise, steep curling drop
        wave = (0.30 * (saw - 0.45) + 0.04 * np.sin(z * TAU / 1.9 + 0.8)) * sstep(1 - r, 0.0, 0.5)
        y = np.maximum(0.0, (Hmax * edge + wave * edge))
        y = np.where(r >= 1.0, 0.0, y)
        rings.append(np.stack([x, y, z], 1))
    rings = np.array(rings)
    # centre point at top: height of the plateau
    top_c = [0, 0.98, zc0]
    P = np.concatenate([[top_c], rings.reshape(-1, 3)])
    F = []
    for j in range(na):
        F.append([0, 1 + (j + 1) % na, 1 + j])
    for i in range(nr - 1):
        for j in range(na):
            j2 = (j + 1) % na
            a, b = 1 + i * na + j, 1 + i * na + j2
            c, d = 1 + (i + 1) * na + j2, 1 + (i + 1) * na + j
            F += [[a, b, c], [a, c, d]]
    # bottom fan (reverse winding), outer ring at y=0
    base_c = len(P)
    P = np.concatenate([P, [[0, 0, zc0]]])
    last = 1 + (nr - 1) * na
    for j in range(na):
        F.append([base_c, last + j, last + (j + 1) % na])
    parts = [finish(P, F)]
    return join(parts)


# ---------------------------------------------------------------- build
def build():
    parts = {
        "plinth": plinth_part(),
        "body": body_part(),
        "tail_fan": tail_fan(),
        "pectoral": pectoral_fins(),
        "mane": mane_part(),
        "face": face_part(),
    }
    return parts


# ---------------------------------------------------------------- preview rasteriser
def render(V, F, az, el, w=1000, h=1300, scale=140.0, smooth=True, target=(0, 4.3, 0.0),
           face_colour=False):
    az, el = np.radians(az), np.radians(el)
    c = np.array([np.sin(az) * np.cos(el), np.sin(el), np.cos(az) * np.cos(el)])
    r = unit(np.cross([0, 1.0, 0], c))
    u = np.cross(c, r)
    tgt = np.asarray(target, float)
    X = (V - tgt) @ r * scale + w / 2
    Y = h / 2 - (V - tgt) @ u * scale
    Zd = (V - tgt) @ c
    tri = trimesh.Trimesh(V, F, process=False)
    fn = tri.face_normals
    if smooth:
        vn = tri.vertex_normals
    L = unit(c * 0.7 + u * 0.7 - r * 0.45)
    zb = np.full((h, w), -1e9, np.float32)
    img = np.zeros((h, w, 3), np.float32)
    img[:] = (0.80, 0.86, 0.93)
    bg = np.zeros((h, w), bool)
    for fi in range(len(F)):
        i0, i1, i2 = F[fi]
        x0, y0, x1, y1, x2, y2 = X[i0], Y[i0], X[i1], Y[i1], X[i2], Y[i2]
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-9:
            continue
        xa, xb = int(max(0, np.floor(min(x0, x1, x2)))), int(min(w - 1, np.ceil(max(x0, x1, x2))))
        ya, yb = int(max(0, np.floor(min(y0, y1, y2)))), int(min(h - 1, np.ceil(max(y0, y1, y2))))
        if xa > xb or ya > yb:
            continue
        gx, gy = np.meshgrid(np.arange(xa, xb + 1) + 0.5, np.arange(ya, yb + 1) + 0.5)
        l0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / den
        l1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / den
        l2 = 1 - l0 - l1
        m = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4)
        if not m.any():
            continue
        z = l0 * Zd[i0] + l1 * Zd[i1] + l2 * Zd[i2]
        sub = zb[ya:yb + 1, xa:xb + 1]
        m &= z > sub
        if not m.any():
            continue
        if smooth:
            n = (l0[..., None] * vn[i0] + l1[..., None] * vn[i1] + l2[..., None] * vn[i2])
            n = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
        else:
            n = np.broadcast_to(fn[fi], gx.shape + (3,))
        facing = (fn[fi] @ c)
        lam = np.clip(n @ L, 0, 1)
        hemi = 0.5 + 0.5 * n[..., 1]
        col = (0.16 + 0.60 * lam + 0.22 * hemi)
        col = np.clip(col, 0, 1)[..., None] * np.array([0.97, 0.96, 0.93])
        if face_colour and facing < 0:
            col = np.broadcast_to(np.array([0.9, 0.1, 0.1]), col.shape)
        sub[m] = z[m]
        sl = img[ya:yb + 1, xa:xb + 1]
        sl[m] = col[m]
    return np.clip(img, 0, 1)


def previews(V, F):
    from PIL import Image
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    views = {
        "front": (0, 8, True), "side": (90, 6, True), "threequarter": (38, 12, True),
        "back": (180, 10, True), "threequarter_back": (215, 14, True),
    }
    sheet = []
    for name, (az, el, sm) in views.items():
        im = render(V, F, az, el, 760, 1000, 104, sm)
        Image.fromarray((im * 255).astype(np.uint8)).save(PREVIEW_DIR / f"{name}.png")
        sheet.append(im)
    # flat-shaded + backface check (red = a flipped face is visible)
    im = render(V, F, 38, 12, 760, 1000, 104, False, face_colour=True)
    Image.fromarray((im * 255).astype(np.uint8)).save(PREVIEW_DIR / "flat_check.png")
    red = ((im[..., 0] > 0.85) & (im[..., 1] < 0.2)).sum()
    # head close-ups
    for name, (az, el) in {"head_front": (15, 6), "head_side": (90, 4), "head_34": (45, 8)}.items():
        im = render(V, F, az, el, 900, 900, 260, True, target=(0, 7.1, 0.3))
        Image.fromarray((im * 255).astype(np.uint8)).save(PREVIEW_DIR / f"{name}.png")
    Image.fromarray((np.concatenate(sheet[:4], 1) * 255).astype(np.uint8)).save(PREVIEW_DIR / "sheet.png")
    return int(red)


def main():
    parts = build()
    V, F = join(list(parts.values()))
    # stand on y=0, centred on the body, top at 8.6
    V = V.copy()
    V[:, 1] -= V[:, 1].min()
    V *= TOP / V[:, 1].max()
    mesh = trimesh.Trimesh(V, F, process=False)
    OUT_OBJ.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(OUT_OBJ)
    print("parts (tris): " + ", ".join(f"{k}={len(f)}" for k, (v, f) in parts.items()))
    print(f"triangles: {len(F)}  vertices: {len(V)}")
    print("bbox min", np.round(V.min(0), 2), "max", np.round(V.max(0), 2))
    bad = 0
    for k, (v, f) in parts.items():
        t = trimesh.Trimesh(v, f, process=False)
        if not (t.is_watertight and t.is_winding_consistent and t.volume > 0):
            bad += 1
            print(f"  WARN part {k}: watertight={t.is_watertight} consistent={t.is_winding_consistent} vol={t.volume:.2f}")
    print("wrote", OUT_OBJ)
    if "--no-preview" not in sys.argv:
        red = previews(V, F)
        print("visible backfaces (px) in the 3/4 flat check:", red, " previews in", PREVIEW_DIR)


if __name__ == "__main__":
    main()
