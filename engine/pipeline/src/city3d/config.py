"""The city's settings: the engine's defaults (defaults.toml), overridden by the region preset the city picks
(presets/<preset>.toml), overridden by the city's own city.toml. Tables merge key by key, anything else
(numbers, strings, lists) is replaced whole.

The city is the folder holding city.toml: named by the CITY3D_CITY environment variable (the file or its
folder), else found from the working directory upwards, as `cd demos/<city> && uv run city3d ...` expects.
Every stage reads its settings once, at import (`CFG = config.get()`), so the CLI loads the city first;
worker processes inherit it (fork) or find it again through CITY3D_CITY, which load() sets.

A city.toml may name more files in a top-level `include = ["generated/structures-m4h.toml", ...]` (paths relative
to the city folder): settings that scripts write (the [[structures]] figures of a city's landmarks), kept out of
city.toml so that it is not rewritten, and committed again, on every tweak of a script. The included files are
layered UNDER city.toml, in list order, then city.toml on top (see `merge_layers`): arrays of tables
([[structures]]) are appended (the included files' entries first, in list order, then city.toml's own), tables
are merged key by key and, on a key set in both, city.toml (the later file) wins. An included file may not
include others. The resolved settings do not show the key; `sources()` lists the files (city.toml first).
"""
import os
import tomllib
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
PRESETS = ENGINE / "presets"
REQUIRED = ("name", "utm_epsg", "districts")

_cfg = None
_sources: list = []


def find(start: Path | None = None) -> Path:
    """The city.toml to use: $CITY3D_CITY (a file or its folder), else the first one from `start` (the working
    directory) upwards."""
    env = os.environ.get("CITY3D_CITY")
    if env:
        p = Path(env).expanduser().resolve()
        return p / "city.toml" if p.is_dir() else p
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / "city.toml").exists():
            return d / "city.toml"
    raise FileNotFoundError("no city.toml here or above; cd into demos/<city> or set CITY3D_CITY")


def merge(base: dict, over: dict) -> dict:
    """Deep merge: tables key by key, everything else from `over`."""
    out = dict(base)
    for k, v in over.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def merge_layers(base: dict, over: dict) -> dict:
    """The merge of an included file under the file that includes it: tables key by key, arrays of tables
    appended (base's entries, then over's), anything else (numbers, strings, plain lists) from `over`."""
    out = dict(base)
    for k, v in over.items():
        b = out.get(k)
        if isinstance(v, dict) and isinstance(b, dict):
            out[k] = merge_layers(b, v)
        elif isinstance(v, list) and isinstance(b, list) and v and b and all(isinstance(x, dict) for x in (*v, *b)):
            out[k] = [*b, *v]
        else:
            out[k] = v
    return out


def read(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def read_city(path: Path) -> dict:
    """city.toml with its `include` files laid under it (see the module docstring); records the files read
    (`sources()`). The `include` key itself is dropped from the result."""
    global _sources
    city = read(path)
    names = city.pop("include", [])
    if isinstance(names, str):
        names = [names]
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ValueError(f"{path}: include must be a list of file names (relative to the city folder)")
    _sources = [path]
    layers = {}
    for n in names:
        f = (path.parent / n).resolve()
        if not f.is_file():
            raise FileNotFoundError(f"{path}: include {n!r}: no file {f} (run the script that writes it)")
        inc = read(f)
        if "include" in inc:
            raise ValueError(f"{f}: an included file may not include others")
        layers = merge_layers(layers, inc)
        _sources.append(f)
    return merge_layers(layers, city)


def sources() -> list:
    """The files the loaded settings came from: city.toml, then its included files in list order."""
    get()
    return list(_sources)


def includes() -> list:
    """The included files only (empty for a city without `include`)."""
    return sources()[1:]


def load(path: Path | str | None = None) -> dict:
    """Load (and cache) the city's resolved settings; `city_dir` is added, `{name}` filled in."""
    global _cfg
    path = Path(path).resolve() if path else find()
    if path.is_dir():
        path = path / "city.toml"
    city = read_city(path)
    defaults = read(ENGINE / "defaults.toml")
    preset = city.get("preset", defaults.get("preset"))
    cfg = defaults
    if preset:
        cfg = merge(cfg, preset_table(preset))
    cfg = merge(cfg, city)
    missing = [k for k in REQUIRED if not cfg.get(k)]
    if missing:
        raise ValueError(f"{path}: missing {', '.join(missing)}")
    cfg = _fill(cfg, {"name": cfg["name"]})
    cfg["title"] = cfg["title"] or cfg["name"]
    cfg["city_dir"] = str(path.parent)
    os.environ["CITY3D_CITY"] = str(path)
    _cfg = cfg
    return cfg


def preset_table(name: str, seen: tuple = ()) -> dict:
    """A region preset's settings. A preset may be built on another (`base = "<preset>"`: that one's tables
    first, this one's merged over them; uk-london on europe-west) and list dotted table names in `replace`
    (e.g. "facade.styles") that it replaces whole instead of merging (London has none of Paris's Haussmann
    styles). Presets without `base` read as before."""
    f = PRESETS / f"{name}.toml"
    if not f.exists():
        raise FileNotFoundError(f"region preset {name!r}: no {f}")
    if name in seen:
        raise ValueError(f"region preset {name!r}: base loop {seen}")
    own = read(f)
    base = own.pop("base", None)
    replace = own.pop("replace", [])
    if not base:
        return own
    out = preset_table(base, seen + (name,))
    for dotted in replace:                 # drop the base's table, so this preset's stands alone
        *path, last = dotted.split(".")
        t = out
        for k in path:
            t = t.get(k) if isinstance(t, dict) else None
        if isinstance(t, dict):
            t.pop(last, None)
    return merge(out, own)


def get() -> dict:
    return _cfg if _cfg is not None else load()


def _fill(v, names):
    """'{name}' in strings -> the city's name."""
    if isinstance(v, dict):
        return {k: _fill(x, names) for k, x in v.items()}
    if isinstance(v, list):
        return [_fill(x, names) for x in v]
    if isinstance(v, str) and "{name}" in v:
        return v.replace("{name}", names["name"])
    return v
