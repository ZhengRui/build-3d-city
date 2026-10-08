"""07_pack: compress the tiles for the viewer with meshopt (EXT_meshopt_compression).

Reads tiles_raw/ in the data folder, writes tiles/ (the folder the viewer loads).
06_tiles.py has already quantized the attributes (KHR_mesh_quantization) and ordered the vertices;
this step only encodes each buffer view with meshopt's vertex and index codecs, which three's
MeshoptDecoder undoes in the browser. Every encoded view is decoded again and compared, since the
Python bindings are young.
"""
import json
import shutil
import struct
from concurrent.futures import ProcessPoolExecutor

import meshoptimizer
import numpy as np

from ..common import DATA, link_web

RAW = DATA / "tiles_raw"
OUT = DATA / "tiles"


def read_glb(path):
    d = path.read_bytes()
    n = struct.unpack("<I", d[12:16])[0]
    gltf = json.loads(d[20:20 + n])
    return gltf, d[20 + n + 8:]


def write_glb(path, gltf, blob: bytes):
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack("<II", len(blob), 0x004E4942)); f.write(blob)


def pack(name: str):
    meshoptimizer.encode_vertex_version(1)       # about 20 % smaller than version 0; three's decoder reads both
    meshoptimizer.encode_index_version(1)
    gltf, raw = read_glb(RAW / name)
    # the uncompressed layout becomes a fallback buffer with no data; views point into it and carry
    # their compressed bytes, stored in buffer 0 (the glb's binary chunk)
    comp = bytearray()
    for view in gltf["bufferViews"]:
        data = raw[view["byteOffset"]:view["byteOffset"] + view["byteLength"]]
        if view.get("target") == 34963:
            size = 4 if _index_type(gltf, view) == 5125 else 2
            idx = np.frombuffer(data, np.uint32 if size == 4 else np.uint16)
            enc = meshoptimizer.encode_index_buffer(idx.astype(np.uint32), len(idx), int(idx.max()) + 1)
            # decode as 32-bit: the bindings mis-shape 16-bit output (the stream is the same for both)
            check = meshoptimizer.decode_index_buffer(len(idx), 4, enc)
            ext = {"byteStride": size, "count": len(idx), "mode": "TRIANGLES"}
            ok = np.array_equal(canonical(np.asarray(check)), canonical(idx))
        else:
            stride = view["byteStride"]
            count = view["byteLength"] // stride
            arr = np.frombuffer(data, np.uint8).reshape(count, stride)
            enc = meshoptimizer.encode_vertex_buffer(arr, count, stride)
            check = meshoptimizer.decode_vertex_buffer(count, stride, enc)
            ext = {"byteStride": stride, "count": count, "mode": "ATTRIBUTES"}
            ok = np.asarray(check).tobytes() == data
        if not ok:
            raise ValueError(f"{name}: meshopt round trip changed buffer view {gltf['bufferViews'].index(view)}")
        while len(comp) % 4:
            comp.append(0)
        view["buffer"] = 1
        view["extensions"] = {"EXT_meshopt_compression": {"buffer": 0, "byteOffset": len(comp),
                                                          "byteLength": len(enc), **ext}}
        comp.extend(enc)
    gltf["buffers"] = [{"byteLength": len(comp) + (-len(comp) % 4)},
                       {"byteLength": len(raw), "extensions": {"EXT_meshopt_compression": {"fallback": True}}}]
    for key in ("extensionsUsed", "extensionsRequired"):
        gltf[key] = gltf.get(key, []) + ["EXT_meshopt_compression"]
    write_glb(OUT / name, gltf, bytes(comp))


def canonical(idx) -> np.ndarray:
    """Triangles rotated to start at their smallest index: the index codec may rotate a triangle's
    corners (keeping its winding), which draws the same thing."""
    t = np.asarray(idx, np.int64).reshape(-1, 3)
    r = t.argmin(1)
    return np.stack([t[np.arange(len(t)), (r + k) % 3] for k in range(3)], 1)


def _index_type(gltf, view) -> int:
    i = gltf["bufferViews"].index(view)
    return next(a["componentType"] for a in gltf["accessors"] if a["bufferView"] == i)


def main():
    OUT.mkdir(exist_ok=True)
    index = json.loads((RAW / "tiles.json").read_text())
    names = [t["file"] for t in index["tiles"]] + [index["ground"]] + ([index["terrain"]] if "terrain" in index else [])
    with ProcessPoolExecutor(8) as ex:
        list(ex.map(pack, names, chunksize=8))
    for f in OUT.glob("*.glb"):
        if f.name not in names:
            f.unlink()
    if "cover" in index:                         # the backdrop's land cover maps (06e_masses), as they are
        inner = index["cover"].get("inner") or {}
        files = [c["file"] for c in (index["cover"], inner, inner.get("lines")) if c]
        for f in files:
            shutil.copy(RAW / f, OUT / f)
        for f in OUT.glob("cover*.*"):
            if f.name not in files:
                f.unlink()
    shutil.copy(RAW / "tiles.json", OUT / "tiles.json")
    link_web("tiles")
    raw = sum((RAW / n).stat().st_size for n in names) / 1e6
    packed = sum((OUT / n).stat().st_size for n in names) / 1e6
    print(f"packed {len(names)} files: {raw:.0f} MB -> {packed:.0f} MB")

