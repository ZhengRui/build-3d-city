"""05b_roads' opt-in [roads] span_ways: listed OSM ways take a decks span as if it were their bridge:name, "<span>
lower" its lower level (Tokyo's Rainbow Bridge); off, nothing is renamed. Run: `uv run pytest tests`.
"""
import os
import subprocess
import sys
import textwrap

CITY = """
name = "spanways"
utm_epsg = 32654
[districts]
"Square" = 1
[paths]
data = "data"
[roads]
decks = { "Harbour Bridge" = { deck = 55.0, lower = 47.0, rail_lower = true } }
EXTRA
"""

PROBE = '''
from city3d.stages import roads
print(sorted(roads.SPAN_WAYS.items()))
ways = [{"id": i, "tags": t, "elevated": True} for i, t in
        ((1, {"highway": "motorway", "name": "Expressway No. 11"}), (2, {"highway": "tertiary"}),
         (3, {"railway": "light_rail", "name": "The Line"}), (4, {"highway": "tertiary"}))]
for w in ways:
    if w["id"] in roads.SPAN_WAYS:
        w["tags"] = {**w["tags"], "bridge:name": roads.SPAN_WAYS[w["id"]]}
print([roads.deck_target(w["tags"]) for w in ways])
'''


def _run(tmp_path, extra):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "city.toml").write_text(CITY.replace("EXTRA", extra))
    env = {**os.environ, "CITY3D_CITY": str(tmp_path / "city.toml")}
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(PROBE)], cwd=tmp_path, env=env, capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout.strip().split("\n")


def test_span_ways(tmp_path):
    off = _run(tmp_path, "")
    assert off == ["[]", "[None, None, None, None]"]
    on = _run(tmp_path, 'span_ways = { "Harbour Bridge" = [1], "Harbour Bridge lower" = [2, 3] }')
    assert on[0] == "[(1, 'Harbour Bridge'), (2, 'Harbour Bridge lower'), (3, 'Harbour Bridge lower')]"
    assert on[1] == "[55.0, 47.0, 47.0, None]"
