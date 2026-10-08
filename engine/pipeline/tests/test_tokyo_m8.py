"""Tokyo M8 opt-ins (7 Oct 2026), each off by default:

1. [ground] masses_ring.edge (stages/masses.py ring_edge): the ring's masses lower and sparser over its last `width` m
   to the outer edge of `file`; tagged heights and the rest of the table untouched; no key, no call.
2. The viewer's opt-ins leave the default shader graph as it was (JS-level choices whose default is the old
   expression): facade.nightSigns (the signs' brightness after dark, 4 and 2.2), masses.roofPalette and
   masses.windowVary (masses.js), ground.townLights.white / farK (ground.js; the same lines as Singapore's M8 fix round).
Run: `uv run pytest tests`.
"""
import json
from pathlib import Path

from test_masses_ring import box_ll, ok, run

VIEWER = Path(__file__).resolve().parents[2] / "viewer"

# the ring's whole extent: 103.80-103.83 (the clip and the ring of test_masses_ring); its outer edge at lon 103.83
EXTENT = box_ll(103.80, 1.30, 103.83, 1.31)


def test_edge_off_by_default(tmp_path):
    out = ok(run(tmp_path, """
        print(json.dumps(masses.RING.get("edge")))
    """, ring='masses_ring = { file = "ring.geojson" }'))
    assert json.loads(out) is None


def test_edge_lowers_and_thins(tmp_path):
    (tmp_path / "extent.geojson").write_text(json.dumps(EXTENT))
    out = ok(run(tmp_path, """
        rows = []
        # 200 untagged ring footprints along a line from 1.3 km inside to ~30 m from the outer edge (lon 103.83),
        # one tagged tower at the edge, one non-ring building at the edge
        for i in range(200):
            lon = 103.8183 + i * (0.0113 / 200)
            r = bld(f"w{1000 + i}", lon, 1.305, w=10)
            r["ring"] = True
            rows.append(r)
        t = bld("w9", 103.8295, 1.306, w=10, h="40"); t["ring"] = True; rows.append(t)
        n = bld("w8", 103.8295, 1.307, w=10); n["ring"] = False; rows.append(n)
        b = gpd.GeoDataFrame(rows, geometry="geometry", crs=UTM)
        b["h"] = 10.0
        b.loc[b["osm"] == "w9", "h"] = 40.0
        e = masses.ring_edge(b, masses.RING["edge"])
        inner = e[e["osm"].isin([f"w{1000 + i}" for i in range(60)])]
        outer = e[e["osm"].isin([f"w{1000 + i}" for i in range(185, 200)])]
        print(json.dumps({"n": len(e), "inner_h": inner["h"].round(3).tolist(), "inner_n": len(inner),
                          "outer_max": float(outer["h"].max()) if len(outer) else None, "outer_n": len(outer),
                          "w9": float(e.loc[e["osm"] == "w9", "h"].iloc[0]), "w8": float(e.loc[e["osm"] == "w8", "h"].iloc[0])}))
    """, ring='masses_ring = { file = "ring.geojson", edge = { file = "extent.geojson", width = 400.0, h = 0.5, thin = 0.6 } }'))
    r = json.loads(out.splitlines()[-1])
    assert r["inner_n"] == 60 and all(h == 10.0 for h in r["inner_h"])      # more than 400 m in (from every side): untouched
    assert r["outer_max"] is not None and r["outer_max"] < 6.5             # the last ~100 m: about half height
    assert r["outer_n"] < 12                                               # and thinned (60 % at the edge)
    assert r["w9"] == 40.0 and r["w8"] == 10.0                             # tagged tower, non-ring kept as they were
    assert r["n"] < 202


def test_viewer_defaults_unchanged():
    facade = (VIEWER / "facade.js").read_text()
    assert "board.mul(signsHere).mul(nightSigns?.screens ?? 4)" in facade
    assert "signboard.colour.mul(signboard.mask).mul(nightSigns?.boards ?? 2.2)" in facade
    assert "billboardBranch = false, nightSigns = null } = {}" in facade
    masses = (VIEWER / "masses.js").read_text()
    assert "if (opts.roofPalette) roofCol = pickPalette(" in masses
    # (without windowVary: the old expression exactly)
    assert ": mix(vec3(0.035, 0.04, 0.045), vec3(0.11, 0.115, 0.12), hash(bay.add(7)));" in masses
    ground = (VIEWER / "ground.js").read_text()
    assert "let TOWN_WHITE = null, TOWN_FAR_K = 1.6" in ground
    assert "TOWN_WHITE ? vec3(...TOWN_WHITE) : LED" in ground
    assert "if (TOWN_WHITE) col = mix(col," in ground


def test_tokyo_settings():
    city = Path(__file__).resolve().parents[5] / "demos" / "tokyo" / "web" / "city.json"
    if not city.exists():
        return
    d = json.loads(city.read_text())
    assert d["facade"]["nightSigns"]["screens"] < 4
    assert d["night"]["windows"]["even"] is True
    assert len(d["masses"]["roofPalette"]) >= 5
