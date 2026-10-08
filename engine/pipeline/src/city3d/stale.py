"""city3d stale: the viewer's layers older than the data they were made from.

Every layer bakes something of its inputs: the rooftop items their building's base on the terrain and its
outline after the road clearance, the trees and cars the ground's height, the markings the roads. A stage run
again on its own (the terrain rebuilt, the roads fixed) leaves the layers after it as they were, and nothing
in the viewer shows it but things floating or sinking: in New York the rooftop items hung tens of metres over
Lower Manhattan after the terrain and the roads were rebuilt without 06c_rooftops. This lists every layer whose
index is older than one of its inputs, with the stage to run again (`city3d all --from <stage>` runs it and
everything after it). 07b_blocks, the last stage, runs it too and warns.
"""
import os
import sys

from . import config
from .common import DATA

# layer index -> (stage that writes it, the data files it is made from)
LAYERS = {
    "tiles_raw": ("06_tiles", ["buildings.gpkg", "roads.gpkg", "terrain.npz", "ground.gpkg"]),
    "tiles_raw/masses.json": ("06e_masses", ["town_buildings.gpkg", "terrain.npz", "buildings.gpkg"]),
    "tiles/tiles.json": ("07_pack", ["tiles_raw"]),
    "markings/markings.json": ("06b_markings", ["roads.gpkg", "terrain.npz"]),
    "shores/shores.json": ("05e_shores", ["terrain.npz", "ground.gpkg"]),
    "trees/trees.json": ("08_trees", ["terrain.npz", "roads.gpkg", "ground.gpkg", "buildings.gpkg"]),
    "cars/cars.json": ("06d_cars", ["roads.gpkg", "terrain.npz"]),
    "rooftops/rooftops.json": ("06c_rooftops", ["buildings.gpkg", "roads.gpkg", "terrain.npz"]),
    "blocks/blocks.json": ("07b_blocks", ["tiles/tiles.json", "markings/markings.json"]),
    "lamps/lamps.json": ("06e_lamps", ["roads.gpkg", "terrain.npz"]),
}


# layers that read the city's [[structures]] (06_tiles: the figures, the bridge decks): also made from the
# `include` files of city.toml, which hold script-written structures; a change to one makes them stale
STRUCTURE_LAYERS = ("tiles_raw",)


def inputs(layer: str, data_inputs: list) -> list:
    """The layer's inputs: its data files (relative to the data folder), and for the layers that read
    [[structures]] the city.toml's included files (absolute paths)."""
    extra = [str(f) for f in config.includes()] if layer in STRUCTURE_LAYERS else []
    return [*data_inputs, *extra]


def mtime(rel: str):
    p = DATA / rel
    if not p.exists():
        return None
    if p.is_dir():                          # a folder: its newest file
        times = [f.stat().st_mtime for f in p.iterdir() if f.is_file()]
        return max(times) if times else None
    return p.stat().st_mtime


def stale() -> list:
    """(layer, stage, the inputs newer than it) for every layer present and older than an input."""
    out = []
    for layer, (stage, files) in LAYERS.items():
        t = mtime(layer)
        if t is None:
            continue
        newer = [i for i in inputs(layer, files) if (mtime(i) or 0) > t + 1]
        if newer:
            out.append((layer, stage, newer))
    return out


def report() -> bool:
    rows = stale()
    for layer, stage, newer in rows:
        names = [os.path.relpath(i, config.get()["city_dir"]) if os.path.isabs(i) else i for i in newer]   # included files: city-relative
        print(f"STALE {layer}: older than {', '.join(names)}; run {stage} again")
    if rows:
        from .stages import plan
        labels = [" ".join([s, *a]) for s, a in plan()]      # ("08_trees" is the full run, after the roads)
        first = min((r[1] for r in rows), key=lambda s: labels.index(s) if s in labels else len(labels))
        print(f"(city3d all --from {first} runs them all again)")
    else:
        print("every layer is newer than its inputs")
    return not rows


def main(argv=None):
    sys.exit(0 if report() else 1)
