"""The pipeline's stages by their familiar names (as the numbered scripts had them), and the order `city3d all`
runs them in. Each stage module has main() (or run(argv) when it takes flags) and reads the city's settings
at import."""
from .. import config

# name -> module in city3d (stages.<m> or sources.<m>)
STAGES = {
    "01_osm": "stages.osm",
    "02_gba": "sources.gba",
    "02_arcgis": "sources.arcgis",
    "02_dem": "stages.dem",
    "02b_eastasia": "sources.eastasia",
    "03_compare": "stages.compare",
    "04_buildings": "stages.buildings",
    "04b_quality": "stages.quality",
    "05_ground": "stages.ground",
    "05a_terrain": "stages.terrain",
    "05b_roads": "stages.roads",
    "05c_landuse": "stages.landuse",
    "05e_shores": "stages.shores",
    "06_tiles": "stages.tiles",
    "06b_markings": "stages.markings",
    "06c_rooftops": "stages.rooftops",
    "06d_cars": "stages.cars",
    "06e_lamps": "stages.lamps",
    "06e_masses": "stages.masses",
    "07_pack": "stages.pack",
    "07b_blocks": "stages.blocks",
    "08_trees": "stages.trees",
}


def all_stages() -> dict:
    """STAGES plus the stages of the sources the city configures through an adapter ([sources.<name>]
    adapter = "file": stage 02_<name>, run by that source's main())."""
    from .. import sources
    return {**STAGES, **{sources.module(n).STAGE: f"source:{n}" for n in sources.configured()}}


# peak memory (GB) of each stage for western Shenzhen (0.2 M buildings, 660 km² of land); `city3d all
# --min-free` waits for this much plus a margin before starting one
PEAK_GB = {"02_gba": 0.7, "03_compare": 0.8, "04_buildings": 1.3, "05a_terrain": 2.4, "05b_roads": 1.2,
           "06_tiles": 1.4, "06b_markings": 1.3, "05e_shores": 1.2, "08_trees": 4.1, "06d_cars": 1.4,
           "06c_rooftops": 1.4}


def plan() -> list:
    """The whole pipeline for the city, in order: (stage, args). The footprint sources' own stages follow
    01_osm, then 02_dem when the DEM adapters can fetch their data; 03_compare runs when a footprint source
    besides OSM carries heights. 08_trees runs twice: once with
    --green-only before 05a_terrain (which reads the green areas it caches; a fresh city has no terrain for
    the rest of it yet), and in full after the roads."""
    from .. import sources
    cfg = config.get()
    fp, hs = cfg["sources"]["footprints"], cfg["sources"]["heights"]
    steps = [("01_osm", [])]
    steps += [(sources.module(n).STAGE, []) for n in fp if n != "osm"]
    dems = {cfg["sources"]["dem"], cfg["sources"]["backdrop"] or cfg["sources"]["dem"]}
    if any(hasattr(sources.module(n), "fetch") for n in dems):
        steps.append(("02_dem", []))
    if any(n != "osm" and sources.module(n).HEIGHTS for n in fp):
        steps.append(("03_compare", []))
    steps += [(s, []) for s in ("04_buildings", "04b_quality", "05_ground", "05c_landuse")]
    steps.append(("08_trees", ["--green-only"]))
    steps += [(s, []) for s in ("05a_terrain", "05b_roads", "06_tiles", *(["06e_masses"] if cfg["ground"]["masses"] else []), "07_pack", "06b_markings", "05e_shores",
                                "08_trees", "06d_cars", "06c_rooftops", "07b_blocks")]
    if cfg.get("lamps", {}).get("path") or cfg.get("lamps", {}).get("generate"):   # an inventory or generated posts
        steps.append(("06e_lamps", []))
    return steps
