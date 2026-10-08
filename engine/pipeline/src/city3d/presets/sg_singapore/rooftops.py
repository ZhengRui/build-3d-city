"""The sg-singapore preset's rooftop clutter (06c_rooftops): china-south's programmes (presets/china_south/rooftops.py)
for Singapore's styles until M6 gives the city its own (HDB's water tanks and lift motor rooms, the condos' pools and
sky gardens): HDB blocks and condos as residential towers, car parks and granite towers as malls and offices, colonial
buildings as civic ones; shophouses and villas carry nothing (their tile roofs and small flat tops).

M5/M6 fix round 1 (critic: blue tanks and boxes on the colonial buildings' pitched tile roofs, the National Gallery's,
Victoria Theatre's, Boat Quay's): a roof with a shape (06_tiles' pitched or mansard roof, ctx "shape") carries
nothing, whatever its style; plant, tanks and units only on flat roofs. Colonial buildings carry nothing at all: the
taller ones (the National Gallery, over the 30 m of roof_shapes' pitched roofs) have flat tops drawn in tile red, where
the real ones have pitched tile roofs and domes with no plant on them.
"""
from ..china_south.rooftops import PROGRAMME as CS


def _nothing(*a):
    return None


def _flat_only(fn):
    """The programme on flat roofs only: a pitched (or mansard) roof keeps its tiles bare."""
    def run(it, roof, rng, y, b):
        if b.get("shape"):
            return None
        return fn(it, roof, rng, y, b)
    return run


PROGRAMME = {k: _flat_only(v) for k, v in {**CS, "hdb": CS["residential"], "condo": CS["residential"],
                                            "carpark": CS["commercial"], "granite": CS["glass"],
                                            }.items()}
PROGRAMME.update({"shophouse": _nothing, "villa": _nothing, "colonial": _nothing})
