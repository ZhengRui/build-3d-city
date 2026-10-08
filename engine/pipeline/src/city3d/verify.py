"""city3d verify: prove a change to the pipeline left its products alone, by comparing this city's data folder
(and checks/) with another copy made before the change.

  city3d verify --against DIR [--data DIR] [--checks DIR --against-checks DIR] [--ignore GLOB,...]

Every file under both folders (raw/ aside) is compared:
  any file            identical bytes: "same"
  gzip (.bin, ...)    else the same once unzipped: "same content" (the header carries a time stamp)
  .npz                else the same arrays: "same arrays" (the zip entries carry time stamps)
  .json               else the same values: "same values"
  .gpkg               per layer: the same columns and rows, attributes equal (NaN = NaN), geometries
                      equals_exact within 1e-6: "same rows" (the file carries time stamps)
  .md (checks)        the same lines once times like "(12 s)" are masked: "same text"
  .png                the same pixels: "same pixels"
Anything else is listed as DIFFERENT with the first difference found; files on one side only as MISSING /
EXTRA. Exit status 1 if anything differs.
"""
import argparse
import fnmatch
import gzip
import json
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

TIMING = re.compile(r"\d+(\.\d+)? ?s\)|\(\d+(\.\d+)? ?s\b")


def compare(a: Path, b: Path) -> tuple:
    """(verdict, detail) for our file a against the reference b."""
    x, y = a.read_bytes(), b.read_bytes()
    if x == y:
        return "same", ""
    if x[:2] == b"\x1f\x8b" and y[:2] == b"\x1f\x8b":
        ux, uy = gzip.decompress(x), gzip.decompress(y)
        return ("same content", "gzip header differs") if ux == uy else ("DIFFERENT", _first(ux, uy))
    suffix = a.suffix.lower()
    if suffix == ".npz":
        return _npz(a, b)
    if suffix == ".json":
        return ("same values", "") if json.loads(x) == json.loads(y) else ("DIFFERENT", "JSON values differ")
    if suffix == ".gpkg":
        return _gpkg(a, b)
    if suffix == ".md":
        lx, ly = (TIMING.sub("<t>", t).splitlines() for t in (x.decode(), y.decode()))
        if lx == ly:
            return "same text", "timings masked"
        d = [f"- {q}\n+ {p}" for p, q in zip(lx, ly) if p != q][:4]
        return "DIFFERENT", f"{sum(p != q for p, q in zip(lx, ly)) + abs(len(lx) - len(ly))} lines:\n" + "\n".join(d)
    if suffix == ".png":
        import matplotlib.image as mpimg
        pa, pb = mpimg.imread(a), mpimg.imread(b)
        return ("same pixels", "") if pa.shape == pb.shape and np.array_equal(pa, pb) else \
            ("DIFFERENT", f"pixels differ ({np.mean(pa != pb) if pa.shape == pb.shape else 'shape'})")
    return "DIFFERENT", _first(x, y)


def _first(x: bytes, y: bytes) -> str:
    n = min(len(x), len(y))
    i = next((k for k in range(n) if x[k] != y[k]), n)
    return f"sizes {len(x):,} / {len(y):,}, first difference at byte {i:,}"


def _npz(a, b):
    da, db = np.load(a), np.load(b)
    if sorted(da.files) != sorted(db.files):
        return "DIFFERENT", f"arrays {sorted(da.files)} / {sorted(db.files)}"
    bad = [k for k in da.files if da[k].dtype != db[k].dtype or not np.array_equal(da[k], db[k], equal_nan=da[k].dtype.kind == "f")]
    return ("same arrays", f"{len(da.files)} arrays") if not bad else ("DIFFERENT", f"arrays differ: {bad}")


def _gpkg(a, b):
    import geopandas as gpd
    import pandas as pd
    import pyogrio
    la, lb = [list(pyogrio.list_layers(p)[:, 0]) for p in (a, b)]
    if la != lb:
        return "DIFFERENT", f"layers {la} / {lb}"
    rows = 0
    for layer in la:
        ga, gb = gpd.read_file(a, layer=layer), gpd.read_file(b, layer=layer)
        if list(ga.columns) != list(gb.columns) or len(ga) != len(gb):
            return "DIFFERENT", f"{layer}: columns/rows {list(ga.columns)} x {len(ga)} / {list(gb.columns)} x {len(gb)}"
        if ga.crs != gb.crs:
            return "DIFFERENT", f"{layer}: crs {ga.crs} / {gb.crs}"
        attrs = [c for c in ga.columns if c != ga.geometry.name]
        try:
            pd.testing.assert_frame_equal(pd.DataFrame(ga[attrs]), pd.DataFrame(gb[attrs]), check_exact=True)
        except AssertionError as e:
            return "DIFFERENT", f"{layer}: attributes: {str(e).splitlines()[0]}"
        eq = ga.geometry.geom_equals_exact(gb.geometry, tolerance=1e-6)
        both_empty = ga.geometry.is_empty & gb.geometry.is_empty
        if not (eq | both_empty).all():
            return "DIFFERENT", f"{layer}: {int((~(eq | both_empty)).sum())} geometries differ"
        rows += len(ga)
    return "same rows", f"{len(la)} layers, {rows:,} rows"


def files(root: Path, ignore) -> set:
    out = set()
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and not rel.startswith("raw/") and not any(fnmatch.fnmatch(rel, g) for g in ignore):
            out.add(rel)
    return out


def _job(args):
    a, b = args
    try:
        return compare(a, b)
    except Exception as e:                                  # an unreadable file is a difference too
        return "DIFFERENT", f"{type(e).__name__}: {e}"


def verify(ours: Path, ref: Path, ignore=(), label="data") -> bool:
    fa, fb = files(ours, ignore), files(ref, ignore)
    common = sorted(fa & fb)
    with ProcessPoolExecutor(4) as ex:
        verdicts = list(ex.map(_job, [(ours / f, ref / f) for f in common], chunksize=16))
    tally = Counter()
    by_kind = {}
    bad = []
    for f, (v, d) in zip(common, verdicts):
        ext = Path(f).suffix or "(none)"
        tally[v] += 1
        by_kind.setdefault(ext, Counter())[v] += 1
        if v == "DIFFERENT":
            bad.append((f, d))
    print(f"## {label}: {ours}\n   against {ref}\n")
    print(f"{len(common):,} files compared: " + ", ".join(f"{n:,} {v}" for v, n in tally.most_common()))
    for ext, c in sorted(by_kind.items()):
        print(f"  {ext:8} " + ", ".join(f"{n:,} {v}" for v, n in c.most_common()))
    for f in sorted(fa - fb):
        print(f"EXTRA    {f}")
    for f in sorted(fb - fa):
        print(f"MISSING  {f}")
    for f, d in bad:
        print(f"DIFFERENT {f}: {d}")
    ok = not bad and fa == fb
    print(f"\n{label}: {'OK, nothing changed' if ok else 'CHANGED'}\n")
    return ok


def main(argv=None):
    from .common import CHECKS, DATA
    ap = argparse.ArgumentParser(prog="city3d verify", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--against", required=True, help="the reference data folder")
    ap.add_argument("--data", default=str(DATA), help="ours (default: the city's data folder)")
    ap.add_argument("--checks", default=str(CHECKS))
    ap.add_argument("--against-checks", help="the reference checks/ folder")
    ap.add_argument("--ignore", default="", help="comma-separated globs (relative paths) to leave out")
    o = ap.parse_args(argv)
    ignore = [g for g in o.ignore.split(",") if g]
    ok = verify(Path(o.data), Path(o.against), ignore, "data")
    if o.against_checks:
        ok &= verify(Path(o.checks), Path(o.against_checks), ignore, "checks")
    sys.exit(0 if ok else 1)
