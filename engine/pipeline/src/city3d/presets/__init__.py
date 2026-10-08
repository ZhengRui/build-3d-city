"""Region presets: what a region's cities share and a city picks with `preset = "<name>"` in city.toml.

Each preset is two files here:
  <name>.toml   tables of settings merged over the engine's defaults.toml (and under the city's city.toml,
                which can override any of them): facade styles and their palettes, OSM tag mappings, road
                widths, sidewalks, tree species, vehicle types, colours and traffic mix, rooftop colours...
  <name>/       (a package; dashes become underscores) the parts that are code, not tables:
                  __init__.py  building_kind(b)       the building kinds (04_buildings)
                               facade_styles(b, use)  the facade style per building (06_tiles)
                  rooftops.py  PROGRAMME              facade style -> function placing a roof's clutter, and
                                                      the items it places (06c_rooftops)

"china-south" is western Shenzhen's: Chinese urban villages, tiled residential towers, glass offices, water
tanks and solar water heaters on the roofs, BYD taxis and buses. "us-northeast" is Manhattan's (brownstones,
brick tenements, setback towers, yellow cabs, wooden water tanks). "europe-west" is Western Europe's (Paris's
tables and rules); "uk-london" (London) and "de-berlin" (Berlin) are built on it (`base`, `replace`: their own facade
styles, roof shapes, shopfronts and rooftop programmes, europe-west's other tables). "hk-hongkong" (Hong Kong) is built on
china-south: its own kinds (per building, LandsD's podiums), public housing, private tower, tong lau, composite,
industrial and colonial styles, china-south's other tables. A new region copies both files
and changes what differs (see references/porting-checklist.md).
"""
import importlib

from .. import config


def module(name: str | None = None, part: str | None = None):
    """The preset's code (the city's preset unless named), or one part of it ("rooftops")."""
    name = (name or config.get()["preset"]).replace("-", "_")
    return importlib.import_module(f"{__name__}.{name}" + (f".{part}" if part else ""))
