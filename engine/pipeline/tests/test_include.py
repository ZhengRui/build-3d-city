"""city.toml's `include` list (config.py): script-written files laid under city.toml, and `city3d stale` reading
them as inputs of the layers that read [[structures]]. Run: `uv run pytest tests`."""
import os
import subprocess
import sys
import textwrap
import time

import pytest

from city3d import config

CITY_TOML = """
name = "inctest"
utm_epsg = 32630
include = ["generated/structures-a.toml", "generated/structures-b.toml"]
[districts]
"West" = 1
[paths]
data = "data"
[roads]
decks = ["Own deck"]
[[structures]]
kind = "figure"
name = "own 1"
[[structures]]
kind = "figure"
name = "own 2"
"""

A = """
# generated
[[structures]]
kind = "figure"
name = "a1"
[[structures.glazing]]
colour = "#fff"
[[structures]]
kind = "figure"
name = "a2"
[roads]
decks = ["Included deck"]
layer_h = 9.5
"""

B = """
[[structures]]
kind = "figure"
name = "b1"
[roads]
layer_h = 1.0
"""


def make_city(root, city_toml=CITY_TOML, a=A, b=B):
    (root / "generated").mkdir(exist_ok=True)
    (root / "city.toml").write_text(city_toml)
    (root / "generated" / "structures-a.toml").write_text(a)
    (root / "generated" / "structures-b.toml").write_text(b)
    return root / "city.toml"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(config, "_cfg", None)
    monkeypatch.setattr(config, "_sources", [])
    monkeypatch.delenv("CITY3D_CITY", raising=False)
    yield
    monkeypatch.delenv("CITY3D_CITY", raising=False)


def test_includes_come_first_in_list_order_then_the_citys_own(tmp_path, env):
    cfg = config.load(make_city(tmp_path))
    assert [s["name"] for s in cfg["structures"]] == ["a1", "a2", "b1", "own 1", "own 2"]
    assert cfg["structures"][0]["glazing"] == [{"colour": "#fff"}]       # nested arrays of tables come along
    assert "include" not in cfg                                         # the key is not part of the settings
    assert [p.name for p in config.sources()] == ["city.toml", "structures-a.toml", "structures-b.toml"]
    assert [p.name for p in config.includes()] == ["structures-a.toml", "structures-b.toml"]


def test_tables_merge_and_the_citys_own_wins_on_a_conflict(tmp_path, env):
    cfg = config.load(make_city(tmp_path))
    assert cfg["roads"]["layer_h"] == 1.0                  # only in the includes: the later include wins over the earlier
    assert cfg["roads"]["decks"] == ["Own deck"]           # plain lists and scalars: city.toml wins whole
    assert cfg["roads"]["grade"] == 0.05                   # the engine's defaults still under it all


def test_a_city_without_include_is_unchanged(tmp_path, env):
    cfg = config.load(make_city(tmp_path, CITY_TOML.replace('include = ["generated/structures-a.toml", "generated/structures-b.toml"]', "")))
    assert [s["name"] for s in cfg["structures"]] == ["own 1", "own 2"]
    assert config.includes() == []


def test_the_include_may_be_a_single_name(tmp_path, env):
    t = CITY_TOML.replace('["generated/structures-a.toml", "generated/structures-b.toml"]', '"generated/structures-b.toml"')
    cfg = config.load(make_city(tmp_path, t))
    assert [s["name"] for s in cfg["structures"]] == ["b1", "own 1", "own 2"]


def test_errors_are_clear(tmp_path, env):
    path = make_city(tmp_path)
    (tmp_path / "generated" / "structures-b.toml").unlink()
    with pytest.raises(FileNotFoundError, match="structures-b.toml"):
        config.load(path)
    (tmp_path / "generated" / "structures-b.toml").write_text('include = ["x.toml"]\n')
    with pytest.raises(ValueError, match="may not include others"):
        config.load(path)
    path = make_city(tmp_path, CITY_TOML.replace('include = ["generated/structures-a.toml", "generated/structures-b.toml"]', "include = 3"))
    with pytest.raises(ValueError, match="include must be a list"):
        config.load(path)


def test_merge_layers_appends_arrays_of_tables_only():
    out = config.merge_layers({"a": [{"x": 1}], "l": [1, 2], "t": {"k": 1, "j": 1}},
                              {"a": [{"x": 2}], "l": [3], "t": {"k": 2}})
    assert out == {"a": [{"x": 1}, {"x": 2}], "l": [3], "t": {"k": 2, "j": 1}}


def test_stale_reads_the_included_files_as_inputs(tmp_path):
    """tiles_raw older than an included file is stale (06_tiles reads the [[structures]] in it); newer is not."""
    path = make_city(tmp_path)
    data = tmp_path / "data"
    (data / "tiles_raw").mkdir(parents=True)
    t0 = time.time() - 1000
    for f in ("buildings.gpkg", "roads.gpkg", "terrain.npz", "ground.gpkg"):
        (data / f).write_text("x")
        os.utime(data / f, (t0, t0))
    (data / "tiles_raw" / "t_0_0.glb").write_text("x")
    os.utime(data / "tiles_raw" / "t_0_0.glb", (t0 + 100, t0 + 100))
    for f in tmp_path.glob("generated/*.toml"):
        os.utime(f, (t0 + 50, t0 + 50))
    os.utime(path, (t0 + 500, t0 + 500))                    # city.toml itself is not an input (as before)
    code = textwrap.dedent("""
        from city3d import stale
        print([(l, s, [i.rsplit("/", 1)[-1] for i in n]) for l, s, n in stale.stale()])
    """)
    env = {**os.environ, "CITY3D_CITY": str(path)}

    def run():
        r = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout.strip().splitlines()[-1]

    assert run() == "[]"
    os.utime(tmp_path / "generated" / "structures-b.toml", (t0 + 200, t0 + 200))
    assert run() == "[('tiles_raw', '06_tiles', ['structures-b.toml'])]"
