"""Regional data source adapters, picked by the city's [sources]:

  footprints  building footprint sources besides OSM, in the order they fill the building table
              (04_buildings): each a module here (or an instance of a configurable adapter, below) with
                STAGE    the stage that fetches and clips it into the data folder (e.g. "02_gba"), run by main()
                ROLE     "primary": authoritative footprints of every building (an official cadastre such as
                         NYC's), chosen before OSM, which then only fills what they lack;
                         "blocks": whole buildings from coarse imagery, kept where compact and not duplicating
                         OSM; "pieces": fine footprints, aligned to OSM per cell, filling what is left;
                         "fill": footprints taken as they are where nothing chosen before covers them
                HEIGHTS  whether it carries heights (column h), which then become the height source of its name
                load()   its footprints in UTM, with h if HEIGHTS
  heights     cnbh: a raster sampled per footprint (sample(g)); overture: lidar heights by OSM id
  dem         copernicus, usgs3dep, ign, geotiff (local files): tiles() and extent() of the DEM the terrain is estimated from, BARE
              when it is bare earth already (a lidar DTM), and fetch() to download (and prepare) it (stage 02_dem)

Configurable adapters (ADAPTERS): one module serving any number of sources, each named in the city's
[sources] with its own table, e.g. two official layers read from files:
    [sources.apur]
    adapter = "file"            # sources/file.py
    path = "footprints/apur/emprise_batie_paris.geojson"
    ...
module(name) then returns the adapter's instance(name), which has the same attributes as a source module
(STAGE "02_<name>", ROLE, HEIGHTS, load(), main()); its stage runs as `city3d 02_<name>`. Adapters: "file" (any
vector file GDAL reads), "citygml" (CityGML LoD2 tiles, read tile by tile: footprints, heights, roof facts).

A new source is a module here plus an entry in FOOTPRINTS (or its own role in 05a_terrain for a DEM); see
the engine README.
"""
import importlib

FOOTPRINTS = {"gba": "gba", "eastasia": "eastasia", "arcgis": "arcgis"}      # name in [sources] footprints -> module
RASTER_HEIGHTS = {"cnbh": "cnbh", "overture": "overture"}   # sampled per footprint (overture: by OSM id)
DEMS = {"copernicus": "copernicus", "usgs3dep": "usgs3dep", "ign": "ign", "geotiff": "geotiff"}
ADAPTERS = {"file": "file", "citygml": "citygml"}     # [sources.<name>] adapter = ... -> module with instance(name)
_instances = {}


def configured() -> dict:
    """The sources the city's [sources] configures through an adapter: name -> adapter."""
    from .. import config
    return {k: v["adapter"] for k, v in config.get()["sources"].items() if isinstance(v, dict) and v.get("adapter")}


def module(name: str):
    table = {**FOOTPRINTS, **RASTER_HEIGHTS, **DEMS}
    if name in table:
        return importlib.import_module(f"{__name__}.{table[name]}")
    adapter = configured().get(name)
    if adapter in ADAPTERS:
        if name not in _instances:
            _instances[name] = importlib.import_module(f"{__name__}.{ADAPTERS[adapter]}").instance(name)
        return _instances[name]
    if adapter:
        raise KeyError(f"source {name!r}: unknown adapter {adapter!r}; known: {', '.join(ADAPTERS)}")
    raise KeyError(f"unknown source {name!r}; known: {', '.join([*table, *configured()])}")


def geotiff_shifts() -> dict:
    """[sources.geotiff] entries' vertical shifts: {resolved path: metres}; {} when no entry has one (or the
    city has no geotiff source), so the DEM is read exactly as before."""
    from .. import config
    g = config.get()["sources"].get("geotiff", {})
    entries = [e for k in ("ground", "backdrop") for e in ([g.get(k)] if isinstance(g.get(k), (str, dict)) else g.get(k, []))]
    if not any(isinstance(e, dict) and e.get("shift") for e in entries):
        return {}
    return module("geotiff").shifts()
