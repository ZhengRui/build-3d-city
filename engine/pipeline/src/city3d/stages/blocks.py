"""07b_blocks: bundle the building tiles and the road markings into gzipped blocks for the viewer.

Reads tiles/ (07_pack.py) and markings/ (06b_markings.py) in the data folder, writes blocks/: per BLOCK x BLOCK m square of the map one file holding the meshopt-compressed
glbs of its building tiles and markings tiles back to back, gzipped (meshopt's streams still compress by
about a third), plus blocks.json listing where each glb lies in its block once unzipped. Some 90 files
instead of about 1700: python's http.server opens a connection per request, which over a network cost
more than the bytes. The viewer loads the blocks nearest the view first and falls back to the separate
tiles when the folder is missing.
"""
import gzip
import json
import math
from collections import defaultdict

from ..common import CFG, DATA, link_web

TILES = DATA / "tiles"
MARKINGS = DATA / "markings"
OUT = DATA / "blocks"
# metres (four by four 1 km tiles; [blocks] size in city.toml). Smaller blocks let the viewer wait for less
# around the start view (Paris M9: 2000, its dense centre put 37 MB in the four 4 km blocks round the Cité)
BLOCK = CFG.get("blocks", {}).get("size", 4000)
# the town masses (06e_masses, files m_*): blocks of their own, LATE m square, marked "late": the viewer loads
# them after the first usable frame, last of all (Paris M7: they were in the near blocks, +2.4 s to usable)
LATE = 12000


def main():
    OUT.mkdir(exist_ok=True)
    tiles = json.loads((TILES / "tiles.json").read_text())["tiles"]
    mpath = MARKINGS / "markings.json"
    markings = json.loads(mpath.read_text())["tiles"] if mpath.exists() else []
    parts = defaultdict(list)                    # block (i, j) -> [(kind, file)]
    for kind, folder, entries in (("tiles", TILES, tiles), ("markings", MARKINGS, markings)):
        for t in entries:
            if kind == "tiles" and t["file"].startswith("m_"):      # (markings tiles are m_<i>_<j> too)
                parts[("late", math.floor(t["x"] / LATE), math.floor(t["z"] / LATE))].append((kind, folder, t["file"]))
                continue
            parts[(math.floor(t["x"] / BLOCK), math.floor(t["z"] / BLOCK))].append((kind, folder, t["file"]))
    blocks = []
    raw_total = gz_total = 0
    for key, items in sorted(parts.items(), key=lambda kv: tuple(str(k) for k in kv[0])):
        late = key[0] == "late"
        i, j = key[-2:]
        blob, listing = bytearray(), []
        for kind, folder, name in items:
            data = (folder / name).read_bytes()
            listing.append([kind, name, len(blob), len(data)])
            blob.extend(data)
        name = f"b_m{i}_{j}.bin" if late else f"b_{i}_{j}.bin"
        packed = gzip.compress(bytes(blob), 9, mtime=0)
        (OUT / name).write_bytes(packed)
        size = LATE if late else BLOCK
        blocks.append({"file": name, "x": i * size, "z": j * size, "bytes": len(packed), "parts": listing,
                       **({"size": LATE, "late": True} if late else {})})
        raw_total += len(blob)
        gz_total += len(packed)
    for f in OUT.glob("b_*.bin"):
        if f.name not in {b["file"] for b in blocks}:
            f.unlink()
    link_web("blocks")
    (OUT / "blocks.json").write_text(json.dumps({"size": BLOCK, "blocks": blocks}, separators=(",", ":")))
    print(f"{len(tiles)} tiles + {len(markings)} markings tiles -> {len(blocks)} blocks: "
          f"{raw_total / 1e6:.1f} MB -> {gz_total / 1e6:.1f} MB gzipped")
    # the last stage: any layer left older than its inputs by a stage run on its own (stale.py)
    from .. import stale
    stale.report()

