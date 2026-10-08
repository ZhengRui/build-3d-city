"""city3d: run the pipeline for the city in the working directory (or --city).

  city3d <stage> [args]          one stage: 01_osm, 02_gba, ... 07b_blocks (city3d list), e.g. 06_tiles --views-only
  city3d all [--from S] [--to S] [--skip S,S] [--min-free GB]
                                 the whole pipeline in order, each stage in its own process, with its time and
                                 peak memory at the end (and in checks/runtimes.md); --min-free GB waits before
                                 each stage until its usual peak (stages.PEAK_GB) plus that much memory is
                                 available (a shared machine)
  city3d list                    the stages and the order `all` runs them in
  city3d config                  the resolved settings (engine defaults < preset < city.toml) as JSON
  city3d stale                   the viewer's layers older than the data they were made from, and the stage
                                 to run again (stale.py; 07b_blocks warns too)
  city3d verify --against DIR [--data DIR] [--checks DIR] [--against-checks DIR]
                                 compare this city's data folder with another copy (see verify.py)
Options before the command:
  --city PATH                    the city.toml or its folder (default: found from the working directory up)
  --overpass-cache DIR           record Overpass answers there and replay them on later runs
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import time

from . import config


def run_stage(name: str, argv: list):
    from .stages import all_stages
    stages = all_stages()
    if name not in stages:
        sys.exit(f"unknown stage {name!r}; city3d list shows them")
    if stages[name].startswith("source:"):         # a source configured through an adapter (sources.ADAPTERS)
        from . import sources
        mod = sources.module(stages[name].split(":", 1)[1])
    else:
        mod = importlib.import_module(f"city3d.{stages[name]}")
    if hasattr(mod, "run"):
        mod.run(argv)
    else:
        if argv:
            sys.exit(f"{name} takes no arguments")
        mod.main()


def available_gb() -> float:
    """MemAvailable from /proc/meminfo (Linux), in GB; infinite elsewhere."""
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1e6
    except OSError:
        pass
    return float("inf")


def run_all(opts):
    from .stages import PEAK_GB, plan
    steps = plan()
    names = [s for s, _ in steps]
    labels = [" ".join([s, *a]) for s, a in steps]

    def at(v):
        """Index of a step by its label as `city3d list` shows it: "08_trees" is the full run after the
        terrain, "08_trees --green-only" the one before."""
        if v not in labels:
            sys.exit(f"unknown step {v!r}; city3d list shows the run order")
        return labels.index(v)

    lo = at(opts.start) if opts.start else 0
    hi = at(opts.stop) if opts.stop else len(names) - 1
    skip = set(filter(None, (opts.skip or "").split(",")))
    rows, t_all = [], time.time()
    for stage, args in steps[lo:hi + 1]:
        if stage in skip:
            continue
        label = " ".join([stage, *args])
        waited, need = 0, (0.5 if args else PEAK_GB.get(stage, 0.5)) + (opts.min_free or 0)
        while opts.min_free is not None and available_gb() < need:
            if not waited:
                print(f"--- {label}: waiting for {need:.1f} GB of free memory ({available_gb():.1f} GB)", flush=True)
            time.sleep(10)
            waited += 10
        print(f"=== {label}", flush=True)
        t0 = time.time()
        p = subprocess.Popen([sys.executable, "-m", "city3d", stage, *args])
        _, status, usage = os.wait4(p.pid, 0)
        p.returncode = os.waitstatus_to_exitcode(status)
        dt = time.time() - t0
        rows.append((label, dt, usage.ru_maxrss / 1e6))
        if p.returncode:
            sys.exit(f"{label} failed (exit {p.returncode}) after {dt:.0f} s")
    lines = ["# Pipeline runtimes (city3d all)", "", "| Stage | time (s) | peak memory (GB) |", "|---|---|---|"]
    lines += [f"| {s} | {t:.1f} | {m:.2f} |" for s, t, m in rows]
    lines += ["", f"Total {time.time() - t_all:.0f} s."]
    from .common import CHECKS
    CHECKS.mkdir(exist_ok=True)
    (CHECKS / "runtimes.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="city3d", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--city")
    ap.add_argument("--overpass-cache")
    ap.add_argument("command")
    ap.add_argument("args", nargs=argparse.REMAINDER)
    opts = ap.parse_args(argv)
    if opts.overpass_cache:
        os.environ["CITY3D_OVERPASS_CACHE"] = os.path.abspath(opts.overpass_cache)
    config.load(opts.city)                  # also sets CITY3D_CITY for the stages' processes
    cmd = opts.command
    if cmd == "all":
        sub = argparse.ArgumentParser(prog="city3d all")
        sub.add_argument("--from", dest="start")
        sub.add_argument("--to", dest="stop")
        sub.add_argument("--skip")
        sub.add_argument("--min-free", type=float, default=None)
        run_all(sub.parse_args(opts.args))
    elif cmd == "list":
        from .stages import all_stages, plan
        print("stages:", ", ".join(all_stages()))
        print("city3d all runs:", " -> ".join(" ".join([s, *a]) for s, a in plan()))
    elif cmd == "config":
        print(json.dumps(config.get(), indent=1, ensure_ascii=False))
    elif cmd == "stale":
        from . import stale
        stale.main(opts.args)
    elif cmd == "verify":
        from . import verify
        verify.main(opts.args)
    else:
        run_stage(cmd, opts.args)


if __name__ == "__main__":
    main()
